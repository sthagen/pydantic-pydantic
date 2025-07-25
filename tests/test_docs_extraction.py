import sys
import textwrap
from dataclasses import dataclass, field
from typing import Annotated, Generic, TypeVar

import pytest
from typing_extensions import TypedDict

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, create_model, with_config
from pydantic.dataclasses import dataclass as pydantic_dataclass

T = TypeVar('T')


def dec_noop(obj):
    return obj


def test_model_no_docs_extraction():
    class MyModel(BaseModel):
        a: int = 1
        """A docs"""

        b: str = '1'

        """B docs"""

    assert MyModel.model_fields['a'].description is None
    assert MyModel.model_fields['b'].description is None


def test_model_docs_extraction():
    # Using a couple dummy decorators to make sure the frame is pointing at
    # the `class` line:
    @dec_noop
    @dec_noop
    class MyModel(BaseModel):
        a: int
        """A docs"""
        b: int = 1

        """B docs"""
        c: int = 1
        # This isn't used as a description.

        d: int

        def dummy_method(self) -> None:
            """Docs for dummy that won't be used for d"""

        e: Annotated[int, Field(description='Real description')]
        """Won't be used"""

        f: int
        """F docs"""

        """Useless docs"""

        g: int
        """G docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    assert MyModel.model_fields['a'].description == 'A docs'
    assert MyModel.model_fields['b'].description == 'B docs'
    assert MyModel.model_fields['c'].description is None
    assert MyModel.model_fields['d'].description is None
    assert MyModel.model_fields['e'].description == 'Real description'
    assert MyModel.model_fields['g'].description == 'G docs'


def test_model_docs_duplicate_class():
    """Ensure source parsing is working correctly when using frames."""

    @dec_noop
    class MyModel(BaseModel):
        a: int
        """A docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    @dec_noop
    class MyModel(BaseModel):
        b: int
        """B docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    assert MyModel.model_fields['b'].description == 'B docs'

    # With https://github.com/python/cpython/pull/106815/ introduced,
    # inspect will fallback to the last found class in the source file.
    # The following is to ensure using frames will still get the correct one
    if True:

        class MyModel(BaseModel):
            a: int
            """A docs"""

            model_config = ConfigDict(
                use_attribute_docstrings=True,
            )

    else:

        class MyModel(BaseModel):
            b: int
            """B docs"""

            model_config = ConfigDict(
                use_attribute_docstrings=True,
            )

    assert MyModel.model_fields['a'].description == 'A docs'


def test_model_docs_dedented_string():
    # fmt: off
    class MyModel(BaseModel):
        def bar(self):
            """
An inconveniently dedented string
            """

        a: int
        """A docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )
    # fmt: on
    assert MyModel.model_fields['a'].description == 'A docs'


def test_model_docs_inheritance():
    class MyModel(BaseModel):
        a: int
        """A docs"""

        b: int
        """B docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    FirstModel = MyModel

    class MyModel(FirstModel):
        a: int
        """A overridden docs"""

    assert FirstModel.model_fields['a'].description == 'A docs'
    assert MyModel.model_fields['a'].description == 'A overridden docs'
    assert MyModel.model_fields['b'].description == 'B docs'


def test_model_different_name():
    # As we extract docstrings from cls in `ModelMetaclass.__new__`,
    # we are not affected by `__name__` being altered in any way.

    class MyModel(BaseModel):
        a: int
        """A docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    MyModel.__name__ = 'OtherModel'

    assert MyModel.model_fields['a'].description == 'A docs'


def test_model_generic():
    class MyModel(BaseModel, Generic[T]):
        a: T
        """A docs"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    assert MyModel.model_fields['a'].description == 'A docs'

    class MyParameterizedModel(MyModel[int]):
        a: int
        """A parameterized docs"""

    assert MyParameterizedModel.model_fields['a'].description == 'A parameterized docs'
    assert MyModel[int].model_fields['a'].description == 'A docs'


def test_dataclass_no_docs_extraction():
    @pydantic_dataclass
    class MyModel:
        a: int = 1
        """A docs"""

        b: str = '1'

        """B docs"""

    assert MyModel.__pydantic_fields__['a'].description is None
    assert MyModel.__pydantic_fields__['b'].description is None


def test_dataclass_docs_extraction():
    @pydantic_dataclass(
        config=ConfigDict(use_attribute_docstrings=True),
    )
    @dec_noop
    class MyModel:
        a: int
        """A docs"""
        b: int = 1

        """B docs"""
        c: int = 1
        # This isn't used as a description.

        d: int = 1

        def dummy_method(self) -> None:
            """Docs for dummy_method that won't be used for d"""

        e: int = Field(1, description='Real description e')
        """Won't be used"""

        if sys.version_info >= (3, 14):
            f: int = field(default=1, doc='Real description f')
            """Won't be used"""

        g: int = 1
        """G docs"""

        """Useless docs"""

        h: int = 1
        """H docs"""

        i = 1
        """I docs, not a field"""

        j: Annotated[int, Field(description='Real description j')] = 1
        """Won't be used"""

    assert MyModel.__pydantic_fields__['a'].description == 'A docs'
    assert MyModel.__pydantic_fields__['b'].description == 'B docs'
    assert MyModel.__pydantic_fields__['c'].description is None
    assert MyModel.__pydantic_fields__['d'].description is None
    assert MyModel.__pydantic_fields__['e'].description == 'Real description e'
    if sys.version_info >= (3, 14):
        assert MyModel.__pydantic_fields__['f'].description == 'Real description f'
    assert MyModel.__pydantic_fields__['g'].description == 'G docs'
    assert MyModel.__pydantic_fields__['h'].description == 'H docs'
    assert MyModel.__pydantic_fields__['j'].description == 'Real description j'

    # https://github.com/pydantic/pydantic/issues/11243:
    # Even though the `FieldInfo` instances had the correct description set,
    # a bug in the core schema generation logic omitted them:
    assert TypeAdapter(MyModel).json_schema()['properties']['a']['description'] == 'A docs'


def test_stdlib_docs_extraction():
    @dataclass
    @with_config({'use_attribute_docstrings': True})
    class MyModel:
        a: int
        """A docs"""

    ta = TypeAdapter(MyModel)

    assert ta.json_schema()['properties']['a']['description'] == 'A docs'


@pytest.mark.xfail(
    condition=sys.version_info < (3, 13),
    reason=(
        'Since Python 3.13, we can leverage the new `__firstlineno__` class attribute, '
        'used by `inspect.getsourcelines().'
    ),
)
def test_stdlib_docs_extraction_duplicate_class():
    @dataclass
    @with_config({'use_attribute_docstrings': True})
    class MyModel:
        a: int
        """A docs"""

    @dataclass
    @with_config({'use_attribute_docstrings': True})
    class MyModel:
        b: int
        """B docs"""

    ta = TypeAdapter(MyModel)
    assert ta.json_schema()['properties']['b']['description'] == 'B docs'

    if True:

        @dataclass
        @with_config({'use_attribute_docstrings': True})
        class MyModel:
            a: int
            """A docs"""

    else:

        @dataclass
        @with_config({'use_attribute_docstrings': True})
        class MyModel:
            b: int
            """B docs"""

    ta = TypeAdapter(MyModel)
    assert ta.json_schema()['properties']['a']['description'] == 'A docs'


@pytest.mark.xfail(reason='Current implementation does not take inheritance into account.')
def test_stdlib_docs_extraction_inheritance():
    @dataclass
    @with_config({'use_attribute_docstrings': True})
    class Base:
        a: int
        """A docs"""

    @dataclass
    @with_config({'use_attribute_docstrings': True})
    class MyStdlibDataclass(Base):
        b: int
        """B docs"""

    ta = TypeAdapter(MyStdlibDataclass)

    assert ta.json_schema() == {
        'properties': {
            'a': {'title': 'A', 'type': 'integer', 'description': 'A docs'},
            'b': {'title': 'B', 'type': 'integer', 'description': 'B docs'},
        },
        'required': ['a', 'b'],
        'title': 'MyStdlibDataclass',
        'type': 'object',
    }


def test_typeddict():
    class MyModel(TypedDict):
        a: int
        """A docs"""

    ta = TypeAdapter(MyModel)
    assert ta.json_schema() == {
        'properties': {'a': {'title': 'A', 'type': 'integer'}},
        'required': ['a'],
        'title': 'MyModel',
        'type': 'object',
    }

    class MyModel(TypedDict):
        a: int
        """A docs"""

        __pydantic_config__ = ConfigDict(use_attribute_docstrings=True)

    ta = TypeAdapter(MyModel)

    assert ta.json_schema() == {
        'properties': {'a': {'title': 'A', 'type': 'integer', 'description': 'A docs'}},
        'required': ['a'],
        'title': 'MyModel',
        'type': 'object',
    }


def test_typeddict_as_field():
    class ModelTDAsField(TypedDict):
        a: int
        """A docs"""

        __pydantic_config__ = ConfigDict(use_attribute_docstrings=True)

    class MyModel(BaseModel):
        td: ModelTDAsField

    a_property = MyModel.model_json_schema()['$defs']['ModelTDAsField']['properties']['a']
    assert a_property['description'] == 'A docs'


def test_create_model_test():
    # Duplicate class creation to ensure create_model
    # doesn't fallback to using inspect, which could
    # in turn use the wrong class:
    class MyModel(BaseModel):
        foo: str = '123'
        """Shouldn't be used"""

        model_config = ConfigDict(
            use_attribute_docstrings=True,
        )

    assert MyModel.model_fields['foo'].description == "Shouldn't be used"

    MyModel = create_model(
        'MyModel',
        foo=(int, 123),
        __config__=ConfigDict(use_attribute_docstrings=True),
    )

    assert MyModel.model_fields['foo'].description is None


def test_exec_cant_be_parsed():
    source = textwrap.dedent(
        '''
        class MyModel(BaseModel):
            a: int
            """A docs"""

            model_config = ConfigDict(use_attribute_docstrings=True)
        '''
    )

    locals_dict = {}

    exec(source, globals(), locals_dict)
    assert locals_dict['MyModel'].model_fields['a'].description is None
