#!/bin/bash
python graylogHUB.py --function-url "$FUNCTION_URL" --port "$GELF_PORT" "$@" 