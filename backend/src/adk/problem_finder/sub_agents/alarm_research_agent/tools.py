"""
Top level agent for data agent multi-agents.
-- get alarm data from database
-- verify the data with rag
"""

from dotenv import load_dotenv
from toolbox_core import ToolboxSyncClient
from google.adk.tools.tool_context import ToolContext

from typing import Dict, List, Union
from vertexai import rag

import os
import json

load_dotenv()

# MCP toolbox for database
# TOOLBOX_URL = os.getenv("MCP_TOOLBOX_URL", "http://127.0.0.1:5000")

# inside the toolbox
# ['compare_daily_inverter_performance', 'get_all_alarms', 'get_daily_plant_summary', 'get_detailed_plant_timeseries', 'get_inverters_alarms', 'list_available_plants', 'list_inverters_for_plant', 'track_single_inverter_performance']
# [0] -> compare_daily_inverter_performance
# [1] -> get_all_alarms
# [2] -> get_daily_plant_summary
# [3] -> get_detailed_plant_timeseries
# [4] -> get_inverters_alarms
# [5] -> list_available_plants
# [6] -> list_inverters_for_plant
# [7] -> track_single_inverter_performance

# Initialize Toolbox client
# toolbox = ToolboxSyncClient(TOOLBOX_URL)
# Load all the tools from toolset
from adk.problem_finder.toolbox import toolbox
fullset_tools = toolbox.load_toolset()
tools = [fullset_tools[1],fullset_tools[4],fullset_tools[6],fullset_tools[7]]

"""
Tool for retrieving device model for `list_corpora`
"""
def get_device_model(plantID: str, date: str, tool_context: ToolContext) -> dict:
    """
    Gets the device model from the database based on plant id.

    Args:
        plantID: The unique ID for the target plant
        date: The target time to investigate
        toolContext: Context for updating session state

    Returns:
        dict: Status and result after executing the tool:
            - action: The name of the tool used
            - problematic_device_model: The device model found
            - message: Brief message about the outcome
    """
    try:
        # get all alarms on the target day and plant
        all_alarms = tools[0](
            plant_id = plantID,
            start_date = date,
            end_date = date
        )

        # parse tool response
        alarm_data = json.loads(all_alarms)
        # extract "target" device id
        device_id = alarm_data[0]["device_id"]

        # get all inverters on the target plant
        all_inverters = tools[2](
            plant_id = plantID,
        )

        data2 = json.loads(all_inverters)
        model = None

        # find the model of the device base on the device_id
        for device in data2:
            if device["device_id"] == device_id:
                model = device["device_model"]

        if "problematic_device_model" not in tool_context.state:
            initial = None
            tool_context.state["problematic_device_model"] = initial

        tool_context.state["problematic_device_model"] = model

        return {
            "action": "get_device_model",
            "problematic_device_model": model,
            "message": f"Device model found: {model}",
        }
    
    except Exception as e:
        return {
            "action": "error",
            "problematic_device_model": None,
            "message": f"Error retrieving device model: {str(e)}",
        }

"""
Tool for listing all available Vertex AI RAG corpora.
"""
def list_corpora(device_model: str, tool_context: ToolContext) -> dict:
    """
    List all available Vertex AI RAG corpora.

    Args:
        device_model: The target device model stored in ToolContext state `problematic_device_model`
        toolContext: Context for updating session state

    Returns:
        dict: A list of available corpora and status, with each corpus containing:
            - status: The status of executing the tool
            - message: Brief message about tool outcome
            - corpus_name: The resource name of the corpus to be queried in the next step
    """
    try:
        corpora = rag.list_corpora()

        # Process corpus information into a more usable format
        corpus_info: List[Dict[str, Union[str, int]]] = []
        for corpus in corpora:
            corpus_data: Dict[str, Union[str, int]] = {
                "resource_name": corpus.name,  # Full resource name for use with other tools
                "display_name": corpus.display_name,
                "create_time": (
                    str(corpus.create_time) if hasattr(corpus, "create_time") else ""
                ),
                "update_time": (
                    str(corpus.update_time) if hasattr(corpus, "update_time") else ""
                ),
            }

            corpus_info.append(corpus_data)

        resourceName = None

        for corpus in corpus_info:
            if corpus["display_name"] == device_model:
                resourceName = corpus["resource_name"]
                break

        if "target_corpus" not in tool_context.state:
            initial = None
            tool_context.state["target_corpus"] = initial

        tool_context.state["target_corpus"] = resourceName
        
        return {
            "status": "success",
            "message": f"Found matching corpora.",
            "corpus_name": resourceName,
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Corpora not found: {str(e)}",
            "corpus_name": [],
        }
    