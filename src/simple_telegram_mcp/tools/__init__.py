import importlib
import inspect
import logging
import os
import pkgutil
from typing import Dict, List, Callable, Any, Coroutine, Optional, Tuple

from mcp.types import Tool, Prompt, TextContent, GetPromptResult

logger = logging.getLogger(__name__)

# --- Registries ---
# These will be populated by the discovery mechanism

TOOL_DEFINITIONS: Dict[str, Tool] = {}
PROMPT_DEFINITIONS: Dict[str, Prompt] = {}

# Type hint for handlers
CallToolHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, List[TextContent]]]
GetPromptHandler = Callable[
    [Optional[Dict[str, Any]]], Coroutine[Any, Any, GetPromptResult]
]
ReadResourceHandler = Callable[[str], Coroutine[Any, Any, str]]  # Takes full URI

TOOL_HANDLERS: Dict[str, CallToolHandler] = {}
PROMPT_HANDLERS: Dict[str, GetPromptHandler] = {}
# Resource handlers might need a more complex key if multiple resources exist
# Using (scheme, netloc) as a key for now
RESOURCE_HANDLERS: Dict[Tuple[str, str], ReadResourceHandler] = {}

# --- Discovery and Registration ---


def register_tools():
    """Discovers and registers tools, prompts, and handlers from this directory."""
    global \
        TOOL_DEFINITIONS, \
        PROMPT_DEFINITIONS, \
        TOOL_HANDLERS, \
        PROMPT_HANDLERS, \
        RESOURCE_HANDLERS

    package_path = os.path.dirname(__file__)
    package_name = os.path.basename(package_path)
    parent_package_name = __name__.split(".")[
        0
    ]  # Get the top-level package name (e.g., simple_telegram_mcp)

    logger.info(f"Discovering tools in package: {parent_package_name}.{package_name}")

    for _, module_name, _ in pkgutil.iter_modules([package_path]):
        if (
            module_name.startswith("_") or module_name == "helpers"
        ):  # Skip __init__, helpers
            continue

        try:
            # Construct the full module path relative to the top-level package
            full_module_name = f"{parent_package_name}.{package_name}.{module_name}"
            module = importlib.import_module(full_module_name)
            logger.debug(f"Imported module: {full_module_name}")

            tool_name = getattr(module, "TOOL_NAME", None)
            if not tool_name:
                logger.warning(
                    f"Module {module_name} missing TOOL_NAME attribute. Skipping."
                )
                continue

            # Register Tool Definition
            tool_def = getattr(module, "tool_definition", None)
            if tool_def and isinstance(tool_def, Tool):
                if tool_def.name != tool_name:
                    logger.warning(
                        f"Mismatch: TOOL_NAME '{tool_name}' vs tool_definition.name '{tool_def.name}' in {module_name}. Using TOOL_NAME."
                    )
                TOOL_DEFINITIONS[tool_name] = tool_def
                logger.debug(f"Registered tool definition: {tool_name}")
            else:
                logger.warning(
                    f"Tool definition not found or invalid type in {module_name} for {tool_name}."
                )

            # Register Prompt Definition
            prompt_def = getattr(module, "prompt_definition", None)
            if prompt_def and isinstance(prompt_def, Prompt):
                if prompt_def.name != tool_name:
                    logger.warning(
                        f"Mismatch: TOOL_NAME '{tool_name}' vs prompt_definition.name '{prompt_def.name}' in {module_name}. Using TOOL_NAME."
                    )
                PROMPT_DEFINITIONS[tool_name] = prompt_def
                logger.debug(f"Registered prompt definition: {tool_name}")
            # else: It's okay if a tool doesn't have a prompt

            # Register Tool Handler
            tool_handler = getattr(module, "handle_call_tool", None)
            if inspect.iscoroutinefunction(tool_handler):
                TOOL_HANDLERS[tool_name] = tool_handler
                logger.debug(f"Registered tool handler: {tool_name}")
            else:
                logger.warning(
                    f"Tool handler 'handle_call_tool' not found or not async in {module_name} for {tool_name}."
                )

            # Register Prompt Handler
            prompt_handler = getattr(module, "handle_get_prompt", None)
            if inspect.iscoroutinefunction(prompt_handler):
                PROMPT_HANDLERS[tool_name] = prompt_handler
                logger.debug(f"Registered prompt handler: {tool_name}")
            # else: It's okay if a tool doesn't have a prompt handler (though less useful)

            # Register Resource Handler
            resource_handler = getattr(module, "handle_read_resource", None)
            if inspect.iscoroutinefunction(resource_handler):
                scheme = getattr(module, "RESOURCE_URI_SCHEME", None)
                netloc = getattr(module, "RESOURCE_URI_NETLOC", None)
                if scheme and netloc:
                    resource_key = (scheme, netloc)
                    if resource_key in RESOURCE_HANDLERS:
                        logger.warning(
                            f"Duplicate resource handler for {resource_key} found in {module_name}. Overwriting."
                        )
                    RESOURCE_HANDLERS[resource_key] = resource_handler
                    logger.debug(f"Registered resource handler for: {resource_key}")
                else:
                    logger.warning(
                        f"Resource handler found in {module_name} but missing RESOURCE_URI_SCHEME or RESOURCE_URI_NETLOC."
                    )
            # else: It's okay if a tool doesn't handle resources

        except ImportError as e:
            logger.error(f"Failed to import module {module_name}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing module {module_name}: {e}", exc_info=True)

    logger.info(f"Tool registration complete. Found {len(TOOL_DEFINITIONS)} tools.")


# --- Accessor Functions ---


def get_all_tools() -> List[Tool]:
    return list(TOOL_DEFINITIONS.values())


def get_all_prompts() -> List[Prompt]:
    return list(PROMPT_DEFINITIONS.values())


def get_tool_handler(name: str) -> Optional[CallToolHandler]:
    return TOOL_HANDLERS.get(name)


def get_prompt_handler(name: str) -> Optional[GetPromptHandler]:
    return PROMPT_HANDLERS.get(name)


def get_resource_handler(scheme: str, netloc: str) -> Optional[ReadResourceHandler]:
    return RESOURCE_HANDLERS.get((scheme, netloc))


# --- Initial Registration ---
# Call this once when the server starts
# register_tools() # This will be called from server.py
