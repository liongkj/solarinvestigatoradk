from google.adk.agents import Agent
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

from .prompts import return_structurer_prompt

class AlarmDetails(BaseModel):
    alarms_found: int
    device_ids: List[str]
    distribution: str
    most_frequent_error: str

class AlarmAnalysisResult(BaseModel):
    executive_summary: List[str] = Field(description=
        """
        Brief overview of alarm investigation results including time period analyzed and devices covered and 
        high-level findings with criticality assessment.
        """
    )
    device_coverage: str = Field(description=
        """
        List of device models found via get_device_model and stored in toolContext state.
        """
    )
    alarm_details: AlarmDetails = Field(description=
        """
        Clearly identifies the total number of alarms found, breakdown by device type/ID and model if applicable,
        chronological distribution of alarms and most frequent error code.
        """
    )
    error_code_analysis: str = Field(description=
        """
        The full analysis for the error code containing:
        - **Resolved Error Codes**: List error codes with available solutions from RAG corpus
        - Include specific error code and affected device model
        - Provide solution summary
        - Note recommended actions
        - **Unresolved Error Codes**: List error codes without available solutions
        - Document error code and affected device model
        - Note frequency and devices affected
        """
    )
    performance_impact: str = Field(description=
        """
        The full analysis for performance impact due to the errors which includes:
        - Correlation between alarms and device performance (when data available)
        - Identification of underperforming devices
        - Timeline of performance degradation if observed
        """
    )
    next_step_recommendation: str = Field(description=
        """
        The full analysis for next step recommendations which includes:
        - Immediate actions required for critical alarms
        - Maintenance scheduling recommendations
        - Further investigation needs for unresolved error codes
        - Performance monitoring recommendations
        """
    )

alarm_structurer_agent = Agent(
    name = "alarm_structurer_agent",
    model = "gemini-2.5-flash-preview-05-20",
    description="Creates structured reports with reports from alarm_research_agent.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2
    ),
    instruction=return_structurer_prompt(),
    output_schema=AlarmAnalysisResult,
    output_key="alarm_agent_output"
) 