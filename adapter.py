import argparse
from env import PersuasionEnv
from bench_common.env_sdk import serve

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    serve(PersuasionEnv, host=args.host, port=args.port)
