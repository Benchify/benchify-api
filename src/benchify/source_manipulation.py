"""
manipulation of the python file
"""
import ast, os, subprocess, sys, pytest
from typing import List, Optional, Set, Dict, Union, Tuple, Any
from stdlib_list import stdlib_list
from pkg_resources import working_set
import importlib.util

def is_system_package(module_name: str) -> bool:
    """
    Determines whether a given module name is part of the Python standard lib.

    Args:
        module_name (str): The name of the module to check.

    Returns:
        bool: True iff the module is part of the Python standard library.
    """
    if " as " in module_name:
        module_name = module_name.split(' as ')[0]
    return module_name in stdlib_list(".".join(map(str, sys.version_info[0:2])))

def is_pip_installed_package(module_name: str) -> bool:
    """
    Determines whether a given module name is pip-installable.

    Args:
        module_name (str): The name of the module to check.

    Returns:
        bool: True iff the module is pip-installable.
    """
    if " as " in module_name:
        module_name = module_name.split(' as ')[0]
    if is_system_package(module_name):
        return False
    if module_name in {pkg.key for pkg in working_set}:
        return True
    return importlib.util.find_spec(module_name) is not None

def find_local_module(module_name: str, file_path: str) -> Optional[str]:
    """
    Finds the path to a locally defined module.
    Args:
        module_name (str): The name of the module to check.
        file_path (str): The path relative to which the module was imported.
    Returns:
        str: The path where the module is defined, or None if it isn't.
    """
    # Split the module name into parts
    module_parts = module_name.split('.')
    
    # Start from the directory of the file being analyzed
    base_dir = os.path.dirname(file_path)
    
    # Recursive function to search for the module
    def search_module(current_dir, remaining_parts):
        if not remaining_parts:
            return None
        
        current_part = remaining_parts[0]
        module_file = os.path.join(current_dir, current_part + '.py')
        module_dir = os.path.join(current_dir, current_part)
        
        if os.path.isfile(module_file):
            # If a module file is found, assume the presence of the remaining parts
            return module_file
        elif os.path.isdir(module_dir):
            init_file = os.path.join(module_dir, '__init__.py')
            if os.path.isfile(init_file):
                result = search_module(module_dir, remaining_parts[1:])
                if result:
                    return result
        
        return None
    
    # Search for the module in the current directory and subdirectories
    result = search_module(base_dir, module_parts)
    if result:
        return result
    
    # Search for the module in the parent directories and their subdirectories
    parent_dir = os.path.dirname(base_dir)
    while parent_dir != base_dir:
        result = search_module(parent_dir, module_parts)
        if result:
            return result
        base_dir = parent_dir
        parent_dir = os.path.dirname(parent_dir)
    
    return None

def get_import_info(
    node: Union[ast.Import, ast.ImportFrom], 
    file_path: str) -> Tuple[str, str]:
    """
    Finds the import info for the given import.
    
    Args:
        node: Either an Import or an ImportFrom in ast.
        file_path (str): The path relative to which the module was imported.
    
    Returns:
        (str0, str1) where str0 is the type of import (local, pip, or system)
        and str2 is the import description (module name or path to module).
    
    Raises:
        ValueError: If no matching import type is found.
    """

    if isinstance(node, ast.Import):
        for alias in node.names:
            module_name = alias.name.strip()
            local_path = find_local_module(module_name, file_path)
            if local_path is not None:
                return ("local", local_path)
            elif is_pip_installed_package(module_name):
                return ("pip", module_name)
            else:
                return ("system", alias.name)
        
        # If no matching import type is found, raise an exception with relevant info
        raise ValueError(f"No matching import type found for module: {alias.name}")
    
    elif isinstance(node, ast.ImportFrom):
        module_name = node.module
        local_path = find_local_module(module_name, file_path)
        if local_path is not None:
            return ("local", local_path)
        if is_pip_installed_package(module_name):
            return ("pip", module_name)
        return ("system", module_name)

def get_import_info_recursive(
    node: Union[ast.Import, ast.ImportFrom],
    file_path: str) -> Dict[Tuple[str, str], Any]:
    """
    Recursively retrieves import information for a given import node and its dependencies.

    Args:
        node (Union[ast.Import, ast.ImportFrom]): The import node to analyze.
        file_path (str): The path of the file containing the import node.

    Returns:
        Dict[Tuple[str, str], Any]: A dictionary mapping import categories and 
        names to their respective import information. The keys are tuples of 
        (category, name), where category is one of "local", "pip", or "system", 
        and name is the name of the imported module or package, or the file path
        for the module if it's locally defined. The values are dictionaries of 
        the same kind.
    """
    import_info = {}

    # Categorize the node using get_import_info
    category, module_file_path_or_name = get_import_info(node, file_path)
    cur_key = (category, module_file_path_or_name)
    import_info[cur_key] = []

    if category == "system" or category == "pip":
        return import_info

    assert category == "local"
    module_ast = None
    
    with open(module_file_path_or_name, "r") as fr:
        module_ast = ast.parse(fr.read())

    for sub in ast.walk(module_ast):
        if isinstance(sub, ast.Import) or isinstance(sub, ast.ImportFrom):
            print("Recursing on sub-import ...")
            sub_import_info = get_import_info_recursive(
                sub, module_file_path_or_name)

            import_info[cur_key].append(sub_import_info)

    return import_info

def build_full_import_map(the_file: str) -> Dict[Tuple[str, str], Any]:
    """
    Calls get_import_info_recursive recursively on each import in the_file and
    returns the resulting dict.

    Args:
        the_file (str): The file we want to analyze.

    Returns:
        Dict[Tuple[str, str], Any]: A dictionary mapping import categories and 
        names to their respective import information. The keys are tuples of 
        (category, name), where category is one of "local", "pip", or "system", 
        and name is the name of the imported module or package, or the file path
        for the module if it's locally defined. The values are dictionaries of 
        the same kind.
    """
    module_ast = None
    
    with open(the_file, "r") as fr:
        module_ast = ast.parse(fr.read())

    import_info = {}
    for sub in ast.walk(module_ast):
        if isinstance(sub, ast.Import) or isinstance(sub, ast.ImportFrom):

            sub_import_info = get_import_info_recursive(sub, the_file)

            import_info |= sub_import_info

    return import_info

def get_top_level_lambda_function_names(ast_tree: ast.AST) -> List[str]:
    """
    Extracts the names of all top-level lambda functions assigned to variables
    from the provided Python code.

    Args:
        ast_tree (ast.AST): The parsed file being studied.

    Returns:
        List[str]: The list of top-level lambda function names.
    """
    lambda_function_names = []
    for node in ast.iter_child_nodes(ast_tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Lambda) and isinstance(node.targets[0], ast.Name):
                lambda_function_names.append(node.targets[0].id)
    return lambda_function_names

def get_all_function_names(code_str: str) -> List[str]:
    """
    Extracts all top-level function names from the provided AST tree.

    Args:
        code_str: The string containing all the code to be analyzed.

    Returns:
        List[str]: The list of top-level function names (def'd or lambda'd) in
        the code_str.
    """
    ast_tree = ast.parse(code_str)
    function_names = []
    for node in ast.iter_child_nodes(ast_tree):
        if isinstance(node, ast.FunctionDef):
            function_names.append(node.name)
    return function_names + get_top_level_lambda_function_names(ast_tree)

def classify(code: str, class_name: str) -> str:
    assert not " " in class_name
    assert not "\t" in class_name

    # Indent the provided code
    indented_code = '\n'.join('    ' + line for line in code.split('\n'))

    # Create the class definition string
    class_code = f"class {class_name}:\n{indented_code}"

    return class_code

def classify_wrap(code: str, class_name: str) -> str:
    assert not " " in class_name
    assert not "\t" in class_name

    classified = classify(code, class_name)

    return classified + "\n" + class_name + " = " + class_name + "()\n"

def normalize_imported_modules_in_code(file_path: str) -> str:
    """
    Normalizes a python code string so that it does not use any aliases in its
    imports.  E.g., would turn "numpy as np" into "np".
    Args:
        file_path: The path to the file that needs to be normalized.
    Returns:
        str: The normalized version of the code string.
    """
    with open(file_path, "r") as fr:
        code_str = fr.read()

    # Parse the code string into an AST
    tree = ast.parse(code_str)
    
    # Create a transformer to modify the AST
    class ImportTransformer(ast.NodeTransformer):
        def __init__(self) -> None:
            self.alias_map: Dict[str, str] = {}
        
        def visit_Import(self, node: ast.Import) -> ast.stmt:
            new_names = []
            for alias in node.names:
                # TODO - change to be recursive
                (import_type, import_name_or_path) = get_import_info(alias.name, file_path)
                if import_type in ["pip", "system"]:
                    # Strip the alias, e.g., "import numpy as np" -> "import numpy"
                    new_names.append(ast.alias(name=alias.name, asname=None))
                else:
                    assert import_type == "local"
                    # Recursively normalize the imported local file
                    normalized_code = normalize_imported_modules_in_code(import_name_or_path)
                    # Run classify_wrap on the normalized code, using the class_name
                    # which is the name of the import (normalized)
                    class_name = alias.asname if alias.asname else alias.name
                    wrapped_code = classify_wrap(normalized_code, class_name)
                    # Parse the wrapped code into an AST
                    wrapped_ast = ast.parse(wrapped_code)
                    # Return the wrapped AST
                    return wrapped_ast.body

            if new_names:
                # Create a new Import node with the stripped aliases
                new_import_node = ast.Import(names=new_names)
                return new_import_node
            else:
                # If no imports remain, return None to remove the import statement
                return None
        
        def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.stmt:
            new_names = []
            for alias in node.names:
                import_node = ast.ImportFrom(module=f"{node.module}.{alias.name}", names=[alias], level=node.level)
                try:
                    (import_type, import_name_or_path) = get_import_info(import_node, file_path)
                    if import_type in ["pip", "system"]:
                        # Normalize "from A import B" to "import A.B" and handle aliases
                        new_name = f"{node.module}.{alias.name}"
                        if alias.asname:
                            self.alias_map[alias.asname] = new_name
                        else:
                            self.alias_map[alias.name] = new_name
                        new_names.append(ast.alias(name=new_name, asname=alias.asname))
                    else:
                        assert import_type == "local"
                        # Recursively normalize the imported local file
                        normalized_code = normalize_imported_modules_in_code(import_name_or_path)
                        # Run classify_wrap on the normalized code, using the class_name
                        # which is the name of the import (normalized)
                        class_name = alias.asname if alias.asname else alias.name
                        wrapped_code = classify_wrap(normalized_code, class_name)
                        # Parse the wrapped code into an AST
                        wrapped_ast = ast.parse(wrapped_code)
                        # Return the wrapped AST
                        return wrapped_ast.body
                except ValueError as e:
                    print(f"Skipping import due to error: {str(e)}")
                    continue

            if new_names:
                # Create a new ImportFrom node with the normalized names
                new_import_from_node = ast.ImportFrom(module=node.module, names=new_names, level=node.level)
                return new_import_from_node
            else:
                # If no imports remain, return None to remove the import statement
                return None
        
        def visit_Name(self, node: ast.Name) -> ast.expr:
            # Replace the usage of aliases with the original module path
            if node.id in self.alias_map:
                module_path = self.alias_map[node.id]
                attrs = module_path.split(".")
                new_node = ast.Name(id=attrs[0], ctx=node.ctx)
                for attr in attrs[1:]:
                    new_node = ast.Attribute(value=new_node, attr=attr, ctx=node.ctx)
                return new_node
            return node
        
        def visit_Attribute(self, node: ast.Attribute) -> ast.expr:
            # Replace the usage of aliases in attribute access
            if isinstance(node.value, ast.Name) and node.value.id in self.alias_map:
                module_path = self.alias_map[node.value.id]
                attrs = module_path.split(".")
                new_node = ast.Name(id=attrs[0], ctx=node.value.ctx)
                for attr in attrs[1:] + [node.attr]:
                    new_node = ast.Attribute(value=new_node, attr=attr, ctx=node.value.ctx)
                return new_node
            return node
    
    # Modify the AST using the transformer
    transformer = ImportTransformer()
    modified_tree = transformer.visit(tree)
    
    # Convert the modified AST back to code string
    normalized_code = ast.unparse(modified_tree)
    
    return normalized_code
    