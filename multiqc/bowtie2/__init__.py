#!/usr/bin/env python

""" MultiQC module to parse output from Bowtie 2 """

from __future__ import print_function
from collections import OrderedDict
import io
import json
import logging
import mmap
import os
import re

import multiqc

class MultiqcModule(multiqc.BaseMultiqcModule):

    def __init__(self, report):

        # Initialise the parent object
        super(MultiqcModule, self).__init__()

        # Static variables
        self.name = "Bowtie 2"
        self.anchor = "bowtie2"
        self.intro = '<p><a href="http://bowtie-bio.sourceforge.net/" target="_blank">Bowtie 2</a> \
            is an ultrafast, memory-efficient short read aligner.</p>'
        self.analysis_dir = report['analysis_dir']
        self.output_dir = report['output_dir']

        # Find and load any Bowtie 2 reports
        self.bowtie2_data = dict()
        for root, dirnames, filenames in os.walk(self.analysis_dir, followlinks=True):
            for fn in filenames:
                if os.path.getsize(os.path.join(root,fn)) < 200000:
                    try:
                        with io.open (os.path.join(root,fn), "r", encoding='utf-8') as f:
                            s = f.read()
                            parsed_data = self.parse_bowtie2_logs(s)
                            if parsed_data is not None:
                                s_name = self.clean_s_name(fn, root, prepend_dirs=report['prepend_dirs'])
                                self.bowtie2_data[s_name] = parsed_data
                    except ValueError:
                        logging.debug("Couldn't read file when looking for Bowtie 2 output: {}".format(fn))

        if len(self.bowtie2_data) == 0:
            logging.debug("Could not find any Bowtie 2 reports in {}".format(self.analysis_dir))
            raise UserWarning

        logging.info("Found {} Bowtie 2 reports".format(len(self.bowtie2_data)))

        # Write parsed report data to a file
        with io.open (os.path.join(self.output_dir, 'report_data', 'multiqc_bowtie2.txt'), "w", encoding='utf-8') as f:
            print( self.dict_to_csv( { k: { j: x for j, x in v.items() if j != 't_lengths'} for k, v in self.bowtie2_data.items() } ), file=f)

        self.sections = list()

        # Basic Stats Table
        # Report table is immutable, so just updating it works
        self.bowtie2_general_stats_table(report)

        # Alignment Rate Plot
        # Only one section, so add to the intro
        self.intro += self.bowtie2_alignment_plot()


    def parse_bowtie2_logs(self, s):
        # Check that this isn't actually Bismark using bowtie
        if s.find('Using bowtie 2 for aligning with bismark.', 0) >= 0: return None
        i = s.find('reads; of these:', 0)
        parsed_data = {}
        if i >= 0:
            regexes = {
                'reads_processed': r"(\d+) reads; of these:",
                'reads_aligned': r"(\d+) \([\d\.]+%\) aligned (?:concordantly )?exactly 1 time",
                'reads_aligned_percentage': r"\(([\d\.]+)%\) aligned (?:concordantly )?exactly 1 time",
                'not_aligned': r"(\d+) \([\d\.]+%\) aligned (?:concordantly )?0 times",
                'not_aligned_percentage': r"\(([\d\.]+)%\) aligned (?:concordantly )?0 times",
                'multimapped': r"(\d+) \([\d\.]+%\) aligned (?:concordantly )?>1 times",
                'multimapped_percentage': r"\(([\d\.]+)%\) aligned (?:concordantly )?>1 times",
                'overall_aligned_rate': r"([\d\.]+)% overall alignment rate",
            }

            for k, r in regexes.items():
                match = re.search(r, s)
                if match:
                    parsed_data[k] = float(match.group(1).replace(',', ''))
            
        if len(parsed_data) == 0: return None
        parsed_data['reads_other'] = parsed_data['reads_processed'] - parsed_data.get('reads_aligned', 0) - parsed_data.get('not_aligned', 0) - parsed_data.get('multimapped', 0)
        return parsed_data


    def bowtie2_general_stats_table(self, report):
        """ Take the parsed stats from the Bowtie 2 report and add it to the
        basic stats table at the top of the report """

        report['general_stats']['headers']['bowtie2_aligned'] = '<th class="chroma-col" data-chroma-scale="OrRd-rev" data-chroma-max="100" data-chroma-min="20"><span data-toggle="tooltip" title="Bowtie 2: overall alignment rate">%&nbsp;Aligned</span></th>'
        for samp, vals in self.bowtie2_data.items():
            report['general_stats']['rows'][samp]['bowtie2_aligned'] = '<td class="text-right">{:.1f}%</td>'.format(vals['overall_aligned_rate'])

    def bowtie2_alignment_plot (self):
        """ Make the HighCharts HTML to plot the alignment rates """

        cats = sorted(self.bowtie2_data.keys())
        data = list()
        keys = OrderedDict()
        keys['reads_aligned'] = '1 Alignment'
        keys['multimapped'] =   '>1 Alignments'
        keys['not_aligned'] =   'Not aligned'
        keys['reads_other'] =   'Other'

        colours = {
            'reads_aligned':  '#8bbc21',
            'multimapped':    '#2f7ed8',
            'not_aligned':    '#0d233a',
            'reads_other':    '#fd0000',
        }

        for k, name in keys.items():
            thisdata = list()
            for sn in cats:
                thisdata.append(self.bowtie2_data[sn].get(k, 0))
            if max(thisdata) > 0:
                data.append({
                    'name': name,
                    'color': colours[k],
                    'data': thisdata
                })

        return '<div class="btn-group switch_group"> \n\
			<button class="btn btn-default btn-sm active" data-action="set_numbers" data-target="#bowtie2_alignment_plot">Number of Reads</button> \n\
			<button class="btn btn-default btn-sm" data-action="set_percent" data-target="#bowtie2_alignment_plot">Percentages</button> \n\
		</div> \n\
        <div id="bowtie2_alignment_plot" class="hc-plot"></div> \n\
        <script type="text/javascript"> \n\
            bowtie2_alignment_cats = {};\n\
            bowtie2_alignment_data = {};\n\
            var bowtie2_alignment_pconfig = {{ \n\
                "title": "Bowtie 2 Alignment Scores",\n\
                "ylab": "# Reads",\n\
                "ymin": 0,\n\
                "stacking": "normal" \n\
            }}; \n\
            $(function () {{ \
                plot_stacked_bar_graph("#bowtie2_alignment_plot", bowtie2_alignment_cats, bowtie2_alignment_data, bowtie2_alignment_pconfig); \
            }}); \
        </script>'.format(json.dumps(cats), json.dumps(data));
