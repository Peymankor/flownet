from typing import Dict, Union, List, Optional

import jinja2
import pandas as pd

from ..utils import write_grdecl_file
from .probability_distributions import UniformDistribution, LogUniformDistribution
from ._base_parameter import Parameter


_TEMPLATE_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.PackageLoader("flownet", "templates"),
    undefined=jinja2.StrictUndefined,
)


class Equilibration(Parameter):
    """
    Parameter type which takes care of stochastically drawn Equilibration parameters.

    Args
        distribution_values:
            A dataframe with five columns ("parameter", "minimum", "maximum",
            "loguniform", "eqlnum") which state:
                * The name of the parameter,
                * The minimum value of the parameter,
                * The maximum value of the parameter,
                * Whether the distribution is uniform of loguniform,
                * To which EQLNUM this applies.
        ti2ci: A dataframe with index equal to tube model index, and one column which equals cell indices.
        eqlnum: A dataframe defining the EQLNUM for each flow tube.
        datum_depth: Depth of the datum (m).

    """

    def __init__(
        self,
        distribution_values: pd.DataFrame,
        ti2ci: pd.DataFrame,
        eqlnum: pd.DataFrame,
        datum_depth: Optional[float] = None,
    ):
        self._datum_depth: Union[float, None] = datum_depth
        self._ti2ci: pd.DataFrame = ti2ci

        self._random_variables = [
            LogUniformDistribution(row["minimum"], row["maximum"])
            if row["loguniform"]
            else UniformDistribution(row["minimum"], row["maximum"])
            for _, row in distribution_values.iterrows()
        ]

        self._unique_eqlnums: List[int] = list(distribution_values["eqlnum"].unique())
        self._parameters: List[Parameter] = list(
            distribution_values["parameter"].unique()
        )
        self._eqlnum: pd.DataFrame = eqlnum

    def get_dims(self) -> Dict:
        """
        Function to export the table dimensions used for memory allocation in Eclipse/Flow.

        Returns:
            Dictionary containing all dimensions to set.

        """
        dims_dict = {"NTEQUL": len(self._unique_eqlnums)}

        return dims_dict

    def render_output(self) -> Dict:
        """
        Creates EQUIL and EQLNUM include content - which are given to the PROPS and GRID section.

        Returns:
            Dictionary with EQUIL and EQLNUM include content.

        """
        merged_df_eqlnum = self._ti2ci.merge(
            self._eqlnum, left_index=True, right_index=True
        )

        parameters = []
        samples_per_eqlnum = len(self.random_samples) // len(self._unique_eqlnums)
        for i, _ in enumerate(self._unique_eqlnums):
            param_value_dict = dict(
                zip(
                    self._parameters,
                    self.random_samples[
                        i * samples_per_eqlnum : (i + 1) * samples_per_eqlnum
                    ],
                )
            )
            parameters.append(param_value_dict)

        return {
            "REGIONS": write_grdecl_file(merged_df_eqlnum, "EQLNUM", int_type=True),
            "SOLUTION": _TEMPLATE_ENVIRONMENT.get_template("EQUIL.jinja2").render(
                {
                    "nr_eqlnum": len(self._unique_eqlnums),
                    "datum_depth": self._datum_depth,
                    "parameters": parameters,
                }
            ),
        }
