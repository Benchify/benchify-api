from src.benchify.source_manipulation import \
    is_system_package, \
    is_pip_installed_package, \
    get_import_info, \
    get_import_info_recursive, \
    build_full_import_map, \
    get_all_function_names, \
    get_top_level_lambda_function_names, \
    normalize_imported_modules_in_code, \
    classify, \
    classify_wrap, \
    find_local_module

import ast

def test_is_system_package():
    assert not is_system_package("auth0-python")
    assert not is_system_package("appdirs")
    assert not is_system_package("pyjwt")
    assert not is_system_package("requests")
    assert not is_system_package("rich")
    assert not is_system_package("typer")
    assert not is_system_package("urllib3")
    assert not is_system_package("stdlib_list")
    assert not is_system_package("pytest")
    assert not is_system_package("pytest")

    assert is_system_package("os")
    assert is_system_package("sys")
    assert is_system_package("re")

    assert not is_system_package("banana hotdog mango !!!")
    assert not is_system_package("")

    exceptions = 0
    try:
        _ = is_system_package(None)
    except Exception as e:
        exceptions = 1
    assert exceptions == 1

def test_is_pip_installed_package():
    assert is_pip_installed_package("auth0-python")
    assert is_pip_installed_package("appdirs")
    assert is_pip_installed_package("pyjwt")
    assert is_pip_installed_package("requests")
    assert is_pip_installed_package("rich")
    assert is_pip_installed_package("typer")
    assert is_pip_installed_package("urllib3")
    assert is_pip_installed_package("stdlib_list")
    assert is_pip_installed_package("pytest")
    assert is_pip_installed_package("pytest")

    assert not is_pip_installed_package("os")
    assert not is_pip_installed_package("sys")
    assert not is_pip_installed_package("re")
    assert not is_pip_installed_package("banana hotdog mango !!!")
    
    exceptions = 0
    try:
        _ = is_pip_installed_package("")
    except Exception as e:
        exceptions += 1
        pass
    
    try:
        _ = is_pip_installed_package(None)
    except Exception as e:
        exceptions += 1
        pass

    assert exceptions == 2

def test_import_info_functions():
    file_path1 = 'tests/fixtures/demo1.py'
    file_path2 = 'tests/fixtures/demo2.py'

    node = ast.Import(names=[ast.alias(name='numpy', asname=None)])
    assert get_import_info(node, file_path1) == ('pip', 'numpy')
    
    node = ast.Import(names=[ast.alias(name='platform', asname='banana_mango')])
    assert get_import_info(node, file_path1) == ('system', 'platform')

    node = ast.ImportFrom(
        module='demo2', 
        names=[ast.alias(name='blarg', asname='super_duper_important')], 
        level=1)
    assert get_import_info(node, file_path1) == ('local', file_path2)

    lhs = { 
        ('local', 'tests/fixtures/demo2.py') : [{
            ('local', 'tests/fixtures/demo3.py') : [{
                ('system', 'os') : []
            }]
        }] 
    }
    rhs = get_import_info_recursive(node, file_path1)
    assert lhs == rhs

    lhs[('system', 'platform')] = []
    lhs[('system', 'sys')] = []
    lhs[('system', 'os')] = []
    lhs[('pip', 'numpy')] = []

    rhs = build_full_import_map(file_path1)
    assert lhs == rhs

def test_get_top_level_lambda_function_names():
    code = '''
banana = lambda x : x + 1
hotdog = lambda x : lambda y : y + x
def shoe(y):
    dilbert = lambda i : i * banana(i)
    return dilbert(y)
'''
    lhs = get_top_level_lambda_function_names(ast.parse(code))
    assert lhs == ['banana', 'hotdog']

def test_get_all_function_names():
    code = '''
def blarg():
    def foo():
        return 5
    return blarg()

bar = lambda x: x + 1

def baz():
    pass
'''
    function_names = get_all_function_names(code)
    print("function names: ", set(function_names))
    assert set(function_names) == {'blarg', 'bar', 'baz'}

def test_get_all_function_names_happy():
    """
    names of both defined functions and named lambda functions retrieved
    no funniness with nested functions or repeated names
    """
    my_example = """
banana = lambda x : "banana"

def hotdog(a, b):
    return a + b
"""
    assert sorted(get_all_function_names(my_example)) == sorted(["banana", "hotdog"])

def test_get_all_function_names():
    """
    names of both defined functions and named lambda functions retrieved
    yes funniness with nested functions or repeated names
    """
    _banana_0 = "banana = lambda x : 'banana'"
    banana_1 = """
def banana(x, y):
    return x * y
"""
    hotdog = """
def hotdog(a, b):
    def banana(x, y):
        return x * y
    return a + b
"""

    my_example = """
banana = lambda x : 'banana'

def hotdog(a, b):
    def banana(x, y):
        return x*y
    return a + b
"""
    assert sorted(get_all_function_names(my_example)) == sorted(["banana", "hotdog"])

def test_classify():
    lhs = """
blarg = 19

x = lambda y : y * 4

def foo(a: str) -> bool:
    return a == "hotdog\"""".strip()

    rhs = """
class mango_time:
    blarg = 19
    
    x = lambda y : y * 4
    
    def foo(a: str) -> bool:
        return a == "hotdog"
""".strip()
    assert classify(lhs, "mango_time") == rhs
    rhs += "\nmango_time = mango_time()\n"
    assert classify_wrap(lhs, "mango_time") == rhs

def test_find_local_module():
    for module1 in ["demo1", "demo2", "demo3"]:
        for module2 in ["demo1", "demo2", "demo3"]:
            if module1 == module2:
                pass
            lhs = find_local_module(module1, "tests/fixtures/" + module2 + ".py")
            rhs = "tests/fixtures/" + module1 + ".py"
            assert lhs == rhs

    lhs = find_local_module("demo2.blarg", "tests/fixtures/demo1.py")
    rhs = "tests/fixtures/demo2.py"
    assert lhs == rhs

# def test_normalize_imported_modules_in_code():
#     normalized_code = normalize_imported_modules_in_code("tests/fixtures/demo1.py")
#     assert normalized_code.strip() == """
# PURPOSE_OF_THIS_FILE = 'just for testing'
# a = 44

# def arbitrary_test_function(foo):
#     print(a)
#     return (demo2.blarg(2 * [PURPOSE_OF_THIS_FILE] + [str(foo)]), platform.system(), sys.platform(), os.name())
# """.strip()
