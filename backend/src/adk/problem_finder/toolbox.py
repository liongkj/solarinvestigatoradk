from toolbox_core import ToolboxSyncClient

TOOLBOX_URL = 'https://agentmcp.liongkj.com'

# Initialize Toolbox client
toolbox = ToolboxSyncClient(TOOLBOX_URL)
# Load all the tools from toolset
tools = toolbox.load_toolset() 