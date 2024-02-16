import inspect

from typing import Union, Callable, List 
from inspect import signature

from langchain.agents import Tool

# All @tool decorated functions in plugins become a CatTool.
# The difference between base langchain Tool and CatTool is that CatTool has an instance of the cat as attribute (set by the MadHatter)
class CatTool(Tool):

    def __init__(self, name: str, func: Callable, description: str, 
                 return_direct: bool = False, examples: List[str] = []):

        # call parent contructor
        super().__init__(name=name, func=func, description=description, return_direct=return_direct)

        # StrayCat instance will be set by AgentManager
        self.cat = None

        self.name = name
        self.return_direct = return_direct
        self.func = func
        self.examples = examples
        self.docstring = self.func.__doc__.strip()
        # remove cat argument from description signature so it does not end up in prompts
        self.description = description.replace(", cat)", ")")

    def __repr__(self) -> str:
        return f"CatTool(name={self.name}, return_direct={self.return_direct}, description={self.docstring})"

    # used by the AgentManager to let a Tool access the cat instance
    def assign_cat(self, cat):
        self.cat = cat

    def _run(self, input_by_llm):
        if inspect.iscoroutinefunction(self.func):
            raise NotImplementedError("Tool does not support sync")

        return self.func(input_by_llm, cat=self.cat)

    async def _arun(self, input_by_llm):
        if inspect.iscoroutinefunction(self.func):
            return await self.func(input_by_llm, cat=self.cat)
        
        return await self.cat.loop.run_in_executor(
            None,
            self.func,
            input_by_llm,
            self.cat
        )

    # override `extra = 'forbid'` for Tool pydantic model in langchain
    class Config:
        extra = "allow"
    # TODO should be: (but langchain does not support yet pydantic 2)
    #model_config = ConfigDict(
    #    extra = "allow"
    #)


# @tool decorator, a modified version of a langchain Tool that also takes a Cat instance as argument
# adapted from https://github.com/hwchase17/langchain/blob/master/langchain/agents/tools.py
def tool(*args: Union[str, Callable], return_direct: bool = False, examples: List[str] = []) -> Callable:
    """
    Make tools out of functions, can be used with or without arguments.
    Requires:
        - Function must be of type (str, cat) -> str
        - Function must have a docstring
    Examples:
        .. code-block:: python
            @tool
            def search_api(query: str, cat) -> str:
                # Searches the API for the query.
                return "https://api.com/search?q=" + query
            @tool("search", return_direct=True)
            def search_api(query: str, cat) -> str:
                # Searches the API for the query.
                return "https://api.com/search?q=" + query
    """

    def _make_with_name(tool_name: str) -> Callable:
        def _make_tool(func: Callable[[str], str]) -> CatTool:
            assert func.__doc__, "Function must have a docstring"
            description = f"{tool_name}{signature(func)}: {func.__doc__.strip()}"
            tool_ = CatTool(
                name=tool_name,
                func=func,
                description=description,
                return_direct=return_direct,
                examples=examples,
            )
            return tool_

        return _make_tool

    if len(args) == 1 and isinstance(args[0], str):
        # if the argument is a string, then we use the string as the tool name
        # Example usage: @tool("search", return_direct=True)
        return _make_with_name(args[0])
    elif len(args) == 1 and callable(args[0]):
        # if the argument is a function, then we use the function name as the tool name
        # Example usage: @tool
        return _make_with_name(args[0].__name__)(args[0])
    elif len(args) == 0:
        # if there are no arguments, then we use the function name as the tool name
        # Example usage: @tool(return_direct=True)
        def _partial(func: Callable[[str], str]) -> CatTool:
            return _make_with_name(func.__name__)(func)

        return _partial
    else:
        raise ValueError("Too many arguments for tool decorator")
