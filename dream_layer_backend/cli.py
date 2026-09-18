import argparse
from config import Config

def main():
    parser = argparse.ArgumentParser(description="CLI for running model with optional safe mode")
    
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for inference")
    parser.add_argument("--precision", type=str, choices=["fp32", "fp16"], default="fp32", help="Precision for inference")
    parser.add_argument("--safe", action="store_true", help="Limit VRAM usage (sets batch size = 1 and precision = fp16)")

    args = parser.parse_args()

    # Create config object from parsed args
    config = Config()

    # Apply overrides if --safe is enabled
    if args.safe:
        config.batch_size = 1
        config.precision = "fp16"
    else:
        config.batch_size = args.batch_size
        config.precision = args.precision

    # Example print just to simulate model execution
    print(f"Running with batch_size={config.batch_size}, precision={config.precision}")

if __name__ == "__main__":
    main()