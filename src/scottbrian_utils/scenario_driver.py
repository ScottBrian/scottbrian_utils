"""scenario_driver.py module."""


class ScenarioVerifier:
    """Class that tracks and verifies the test cases."""

    def __init__(
        self,
        group_name: str,
    ) -> None:
        """Initialize the ConfigVerifier.

        Args:
            group_name: name of group for this ConfigVerifier

        """
        self.specified_args = locals()  # used for __repr__, see below
        self.group_name = group_name
