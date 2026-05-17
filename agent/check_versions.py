import sys
from importlib.metadata import version, PackageNotFoundError

# List of package names you want to check
package_names = [
    "fastapi",
    "uvicorn",
    "python-decouple",
    "python-dotenv",
    "langchain",
    "langgraph",
    "langchain_openai",
    "langchain_community",
    "langchain-anthropic",
    "httpx",
    "ag-ui-protocol",
    "copilotkit"
]

# Print the Python version
print("Python Version:", sys.version)

# Print the version of each package in the list
for package_name in package_names:
    try:
        package_version = version(package_name)
        print(f"{package_name} Version: {package_version}")
    except PackageNotFoundError:
        print(f"{package_name} is not installed")
