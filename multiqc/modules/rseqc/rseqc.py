import logging

from multiqc import config
from multiqc.base_module import BaseMultiqcModule, ModuleNoSamplesFound

log = logging.getLogger(__name__)


class MultiqcModule(BaseMultiqcModule):
    """
    The module parses results generated by RSeQC, a package that provides a number of useful modules that can
    comprehensively evaluate high throughput RNA-seq data.

    Supported scripts:

    - `bam_stat`
    - `gene_body_coverage`
    - `infer_experiment`
    - `inner_distance`
    - `junction_annotation`
    - `junction_saturation`
    - `read_distribution`
    - `read_duplication`
    - `read_gc`
    - `tin`

    You can choose to hide sections of RSeQC output and customise their order. To do this, add and customise
    the following to your MultiQC config file:

    ```yaml
    rseqc_sections:
      - read_distribution
      - tin
      - gene_body_coverage
      - inner_distance
      - read_gc
      - read_duplication
      - junction_annotation
      - junction_saturation
      - infer_experiment
      - bam_stat
    ```

    Change the order to rearrange sections or remove to hide them from the report.

    Note that some scripts (for example, `junction_annotation.py`) write the logs to stderr. To make a file
    parable by MultiQC, redirect the stderr to a file using `2> mysample.log`.
    """

    def __init__(self):
        super(MultiqcModule, self).__init__(
            name="RSeQC",
            anchor="rseqc",
            href="http://rseqc.sourceforge.net/",
            info="Evaluates high throughput RNA-seq data.",
            doi="10.1093/bioinformatics/bts356",
        )

        # Get the list of submodules (can be customised)
        rseqc_sections = getattr(config, "rseqc_sections", [])
        if len(rseqc_sections) == 0:
            rseqc_sections = [
                "read_distribution",
                "gene_body_coverage",
                "inner_distance",
                "read_gc",
                "read_duplication",
                "junction_annotation",
                "junction_saturation",
                "infer_experiment",
                "bam_stat",
                "tin",
            ]

        # Call submodule functions
        n = dict()
        for sm in rseqc_sections:
            try:
                # Import the submodule and call parse_reports()
                #   Function returns number of parsed logs
                module = __import__(f"multiqc.modules.rseqc.{sm}", fromlist=[""])
                n[sm] = getattr(module, "parse_reports")(self)
                if n[sm] > 0:
                    log.info(f"Found {n[sm]} {sm} reports")
            except (ImportError, AttributeError):
                log.error(f"Could not find RSeQC Section '{sm}'")

        # Exit if we didn't find anything
        if sum(n.values()) == 0:
            raise ModuleNoSamplesFound
