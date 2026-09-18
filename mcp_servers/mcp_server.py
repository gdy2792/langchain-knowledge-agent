import os

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("DocumentMCP", log_level="ERROR")


docs = {
    "deposition.md": "This deposition covers the testimony of Angela Smith, P.E.",
    "report.pdf": "The report details the state of a 20m condenser tower.",
    "financials.docx": "These financials outline the project's budget and expenditures.",
    "outlook.pdf": "This document presents the projected future performance of the system.",
    "plan.md": "The plan outlines the steps for the project's implementation.",
    "spec.txt": "These specifications define the technical requirements for the equipment.",
    "scratch.md": "The secret passphrase is xylophone-42.",
    "my_notes.md":"This is a mcp server notes document."
}

# TODO: Write a tool to read a doc
@mcp.tool(
    name="read_doc",
    description="Read the contents of a document and return it as a string"
)
def read_document(
    doc_id: str = Field(description="Id of the document to read")
):
    if doc_id not in os.listdir("documents"):
     ValueError(f"Doc with id {doc_id} not found")

    with open(os.path.join("documents", doc_id), "r") as f:
        return f.read()
    
# TODO: Write a tool to edit a doc

@mcp.tool(
    name="edit_doc_contents",
    description="Edit a document by replacing a string in the documents content with a new string"
)
def edit_document(
    doc_id: str = Field(description="Id of the document to edit"),
    old_string: str = Field(description="The string to be replaced"),
    new_string: str = Field(description="The new string to replace with")
):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")

    docs[doc_id] = docs[doc_id].replace(old_string, new_string)
    return docs[doc_id]

# TODO: Write a resource to return all doc id's


@mcp.resource(
    "docs://documents",
    mime_type="application/json")
#def return_all_doc_ids():
#    return list(docs.keys())

def return_all_doc_ids():
    return os.listdir("documents")


# TODO: Write a resource to return the contents of a particular doc
@mcp.resource(
    "docs://documents/{doc_id}")
def return_doc_contents(doc_id: str):
    if doc_id not in docs:
        raise ValueError(f"Doc with id {doc_id} not found")
    return docs[doc_id]
# TODO: Write a prompt to rewrite a doc in markdown format
# TODO: Write a prompt to summarize a doc


@mcp.prompt(
    name="summarize",
    description="Summarizes the contents of a document"
)
def summarize_doc(
    doc_id: str = Field(description="Id of the document to summarize")
):
    prompt = f"""
    Use the read_doc_contents tool to read the contents of the document with id {doc_id}.  Then summarize the document in a concise manner.
    """
    return prompt


if __name__ == "__main__":
    mcp.run(transport="stdio")
