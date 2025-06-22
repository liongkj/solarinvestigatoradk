from google.adk.tools.tool_context import ToolContext


def append_problematic_rows(rows: str, tool_context: ToolContext):
    """tools to store problematic rows
    parameters
    String rows : the json response for the problematic five minutes data eg. "{problematic_detailed_inverter_performance : [row_data_here] ,analysis : "A general explaination on why you think these data is abnormal}"
    """

    problematic_detailed_inverter_settings = tool_context.state.get(
        "problematic_detailed_inverter_performance"
    )
    problematic_detailed_inverter_settings.append(rows)
    tool_context.state["problematic_detailed_inverter_performance"] = (
        problematic_detailed_inverter_settings
    )
