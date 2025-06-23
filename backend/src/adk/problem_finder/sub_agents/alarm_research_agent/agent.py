# import vertexai libs
from vertexai import rag
from google.genai import types
from google.adk.tools.tool_context import ToolContext
from google.adk.agents.callback_context import CallbackContext
import vertexai
from google.adk.agents import Agent
from adk.callbacks import summarize_agent_output_callback

import os
from dotenv import load_dotenv

from .tools import tools
from .tools import list_corpora, get_device_model
from .prompts import rag_prompt_v7

# load env
load_dotenv()

# define project constants
CORPUS_NAME = "projects/agenthack-461707/locations/us-central1/ragCorpora/864691128455135232"
DEFAULT_TOP_K = 3
DEFAULT_DISTANCE_THRESHOLD = 0.5
DEFAULT_EMBEDDING_MODEL = "publishers/google/models/text-embedding-005"
DEFAULT_EMBEDDING_REQUESTS_PER_MIN = 1000

# get env constants
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

# initialize vertexai API
vertexai.init(project=PROJECT_ID, location=LOCATION)

# prepare rag retrieval config
rag_retrieval_config = rag.RagRetrievalConfig(
    top_k=DEFAULT_TOP_K,
    filter=rag.Filter(vector_distance_threshold=DEFAULT_DISTANCE_THRESHOLD),
)

# create agent tool
def rag_query_all(query: str) -> dict:

    try:

        # perform query
        response = rag.retrieval_query(
                rag_resources=[
                    rag.RagResource(
                        rag_corpus=CORPUS_NAME
                    )
                ],
                text=query,
                rag_retrieval_config=rag_retrieval_config
            )
        
        # Process the response into a more usable format
        results = []
        if hasattr(response, "contexts") and response.contexts:
            for ctx_group in response.contexts.contexts:
                result = {
                    "source_uri": (
                        ctx_group.source_uri if hasattr(ctx_group, "source_uri") else ""
                    ),
                    "source_name": (
                        ctx_group.source_display_name
                        if hasattr(ctx_group, "source_display_name")
                        else ""
                    ),
                    "text": ctx_group.text if hasattr(ctx_group, "text") else "",
                    "score": ctx_group.score if hasattr(ctx_group, "score") else 0.0,
                }
                results.append(result)

        # If we didn't find any results
        if not results:
            return {
                "status": "warning",
                "message": f"No results found in corpus '{CORPUS_NAME}' for query: '{query}'",
                "query": query,
                "corpus_name": CORPUS_NAME,
                "results": [],
                "results_count": 0,
            }

        return {
            "status": "success",
            "message": f"Successfully queried corpus '{CORPUS_NAME}'",
            "query": query,
            "corpus_name": CORPUS_NAME,
            "results": results,
            "results_count": len(results),
        }
    
    except Exception as e:
        error_msg = f"Error querying corpus: {str(e)}"
        return {
            "status": "error",
            "message": error_msg,
            "query": query,
            "corpus_name": CORPUS_NAME,
        }
    
def rag_query_corpus(query: str, tool_context: ToolContext) -> dict:
    """Returns a dict containing the status and information after querying a specific corpus.

    Args:
        query (str): The query to search the corpus.

    Returns:
        A dictionary containing along with the query results from the target corpus.
    
    """

    try:
        corpus_name = None
        if "target_corpus" in tool_context.state:
            corpus_name = tool_context.state.get("target_corpus")

        # perform query
        response = rag.retrieval_query(
                rag_resources=[
                    rag.RagResource(
                        rag_corpus=corpus_name
                    )
                ],
                text=query,
                rag_retrieval_config=rag_retrieval_config
            )
        
        # Process the response into a more usable format
        results = []
        if hasattr(response, "contexts") and response.contexts:
            for ctx_group in response.contexts.contexts:
                result = {
                    "source_uri": (
                        ctx_group.source_uri if hasattr(ctx_group, "source_uri") else ""
                    ),
                    "source_name": (
                        ctx_group.source_display_name
                        if hasattr(ctx_group, "source_display_name")
                        else ""
                    ),
                    "text": ctx_group.text if hasattr(ctx_group, "text") else "",
                    "score": ctx_group.score if hasattr(ctx_group, "score") else 0.0,
                }
                results.append(result)

        # If we didn't find any results
        if not results:
            return {
                "status": "warning",
                "message": f"No results found in corpus '{CORPUS_NAME}' for query: '{query}'",
                "query": query,
                "corpus_name": CORPUS_NAME,
                "results": [],
                "results_count": 0,
            }

        return {
            "status": "success",
            "message": f"Successfully queried corpus '{CORPUS_NAME}'",
            "query": query,
            "corpus_name": CORPUS_NAME,
            "results": results,
            "results_count": len(results),
        }
    
    except Exception as e:
        error_msg = f"Error querying corpus: {str(e)}"
        return {
            "status": "error",
            "message": error_msg,
            "query": query,
            "corpus_name": CORPUS_NAME,
        }
    
def state_setup(callback_context: CallbackContext):
    if "alarm_report" not in callback_context.state:
        callback_context.state["alarm_report"] = None


alarm_research_agent = Agent(
    name="alarm_research_agent",
    # model="gemini-2.0-flash",
    model="gemini-2.5-flash-preview-05-20",
    description="Vertex AI RAG Agent",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2
    ),
    tools=[get_device_model,
           list_corpora,
           rag_query_corpus,
           rag_query_all,
           tools[0],
           tools[1],
           tools[2],
           tools[3],
           ],
    instruction=rag_prompt_v7(),
    output_key="alarm_agent_output",
    before_agent_callback=state_setup,
    after_agent_callback=summarize_agent_output_callback,

)
