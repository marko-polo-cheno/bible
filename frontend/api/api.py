from .search import parse_passages

def handler(request):
    query = request.args.get("query", "")
    if not query:
        return {"error": "Missing query parameter"}, 400, {"Access-Control-Allow-Origin": "*"}

    result = parse_passages(query)
    response = {
        "passages": [p.model_dump_json() for p in result.passages],
        "secondary_passages": [p.model_dump_json() for p in result.secondary_passages],
    }
    return response, 200, {"Access-Control-Allow-Origin": "*"}
