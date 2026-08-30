from typing import Callable, Optional, Type as PyType

from mypy.nodes import CallExpr, NameExpr, KeywordExpr
from mypy.plugin import Plugin, AttributeContext, MethodContext
from mypy.types import Instance, Type as MypyType, TypeType


class ValidatedAttributePlugin(Plugin):
    def get_attribute_hook(
        self, fullname: str
    ) -> Optional[Callable[[AttributeContext], MypyType]]:
        """Intercepts instance attribute access (e.g., instance.shares)."""
        return validate_attribute_callback

    def get_method_hook(
        self, fullname: str
    ) -> Optional[Callable[[MethodContext], MypyType]]:
        """Intercepts descriptor creation (e.g., NumValue(gte=1)) during class definition."""
        if "NumValue.__init__" in fullname:
            return numvalue_init_callback
        return None


def validate_attribute_callback(ctx: AttributeContext) -> MypyType:
    """Ensures that when accessing the attribute on an instance, it evaluates

    to the internal wrapped generic type T (int or float) instead of the descriptor class.
    """
    if isinstance(ctx.type, Instance) and ctx.type.type.has_base("ValidatedAttribute"):
        if ctx.type.args:
            return ctx.type.args[0]  # Returns the 'int' or 'float' type variable
    return ctx.default_attr_type


def numvalue_init_callback(ctx: MethodContext) -> MypyType:
    """Analyzes the arguments passed to NumValue() at static compile time

    to enforce whether it resolves to NumValue[int] or NumValue[float].
    """
    # Default fallback type provided by Mypy
    fallback_type = ctx.default_return_type

    if not isinstance(ctx.context, CallExpr):
        return fallback_type

    # Extract all keyword arguments passed to the constructor
    kwargs = {arg.name: arg for arg in ctx.context.args if isinstance(arg, KeywordExpr)}

    # 1. Check if type_spec was explicitly provided
    if "type_spec" in kwargs:
        type_spec_node = kwargs["type_spec"].expr
        if isinstance(type_spec_node, NameExpr):
            if type_spec_node.name == "float":
                return _build_numvalue_instance(ctx, "float")
            elif type_spec_node.name == "int":
                return _build_numvalue_instance(ctx, "int")

    # 2. If no type_spec, infer from boundary keyword value types
    boundary_keys = ["gt", "gte", "lt", "lte"]
    found_float = False
    found_any_bound = False

    for key in boundary_keys:
        if key in kwargs:
            found_any_bound = True
            # Get the static type inferred for the argument expression
            arg_type = ctx.api.type_context[-1] if ctx.api.type_context else None
            # Fallback evaluation of literal expressions or inferred node types
            expr_type = ctx.api.accept(kwargs[key].expr)

            if isinstance(expr_type, Instance):
                if expr_type.type.fullname == "builtins.float":
                    found_float = True
                    break

    if found_any_bound:
        if found_float:
            return _build_numvalue_instance(ctx, "float")
        else:
            return _build_numvalue_instance(ctx, "int")

    # If everything is completely ambiguous, default back to standard resolution
    return fallback_type


def _build_numvalue_instance(ctx: MethodContext, type_name: str) -> Instance:
    """Helper function to build a specific NumValue[int] or NumValue[float] type."""
    type_info = ctx.api.lookup_fully_qualified(f"builtins.{type_name}")
    descriptor_info = ctx.api.lookup_fully_qualified(
        "validators.NumValue"
    )  # Adjust to your real module path

    if type_info and descriptor_info and isinstance(descriptor_info.node, type):
        generic_arg = Instance(type_info.node, [])
        return Instance(descriptor_info.node, [generic_arg])

    return ctx.default_return_type


def plugin(version: str) -> PyType[Plugin]:
    return ValidatedAttributePlugin
