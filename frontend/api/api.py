from .search import parse_passages

def handler(request):
    headers = {"Access-Control-Allow-Origin": "*"}
    try:
        query = request.args.get("query", "")
        if not query:
            return {"error": "Missing query parameter"}, 400, headers

        result = parse_passages(query)
        response = {
            "passages": [p.model_dump() for p in result.passages],
            "secondary_passages": [p.model_dump() for p in result.secondary_passages],
        }
        return response, 200, headers
    except Exception as e:
        return {"error": str(e)}, 500, headers
