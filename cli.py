"""Command line interface for the restaurant video analysis system."""

import argparse
import json
from pathlib import Path
from main import RestaurantVideoProcessor

def process_single_restaurant(args):
    """Process a single restaurant from command line arguments."""
    processor = RestaurantVideoProcessor()
    
    result = processor.process_restaurant(
        restaurant_name=args.name,
        address=args.address,
        phone=args.phone,
        days_back=args.days_back,
        min_quality_score=args.min_score
    )
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Results saved to {args.output}")

def process_restaurants_from_file(args):
    """Process restaurants from a JSON file."""
    if not Path(args.file).exists():
        print(f"Error: File {args.file} not found")
        return
    
    with open(args.file, 'r') as f:
        restaurants = json.load(f)
    
    if not isinstance(restaurants, list):
        print("Error: JSON file must contain a list of restaurant objects")
        return
    
    processor = RestaurantVideoProcessor()
    results = processor.process_restaurants_batch(
        restaurants,
        days_back=args.days_back,
        min_quality_score=args.min_score
    )
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {args.output}")

def main():
    parser = argparse.ArgumentParser(description='Restaurant Video Analysis System')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Single restaurant command
    single_parser = subparsers.add_parser('single', help='Process a single restaurant')
    single_parser.add_argument('--name', required=True, help='Restaurant name')
    single_parser.add_argument('--address', required=True, help='Restaurant address')
    single_parser.add_argument('--phone', required=True, help='Restaurant phone number')
    single_parser.add_argument('--days-back', type=int, default=30, help='Days back to search for videos')
    single_parser.add_argument('--min-score', type=float, default=5.0, help='Minimum quality score for approval')
    single_parser.add_argument('--output', help='Output file for results')
    
    # Batch processing command
    batch_parser = subparsers.add_parser('batch', help='Process restaurants from file')
    batch_parser.add_argument('--file', required=True, help='JSON file with restaurant data')
    batch_parser.add_argument('--days-back', type=int, default=30, help='Days back to search for videos')
    batch_parser.add_argument('--min-score', type=float, default=5.0, help='Minimum quality score for approval')
    batch_parser.add_argument('--output', help='Output file for results')
    
    args = parser.parse_args()
    
    if args.command == 'single':
        process_single_restaurant(args)
    elif args.command == 'batch':
        process_restaurants_from_file(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()