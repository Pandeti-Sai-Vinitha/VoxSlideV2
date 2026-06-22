#!/usr/bin/env python
"""
Simple wrapper: PPT + voiceover.json → Video with TTS

Usage:
    python run_voiceover.py --ppt <path_to_pptx> --voiceover <path_to_voiceover.json>
"""

import sys
import argparse
from pathlib import Path
from main1 import process_ppt_to_voiceover_video

def main():
    parser = argparse.ArgumentParser(
        description="Convert PPT + voiceover.json to video with speech"
    )
    
    parser.add_argument(
        "--ppt",
        "-p",
        required=True,
        help="Path to PPTX file"
    )
    
    parser.add_argument(
        "--voiceover",
        "-v",
        required=True,
        help="Path to voiceover.json file"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output directory (optional)"
    )
    
    parser.add_argument(
        "--voice",
        default=None,
        help="Azure voice (e.g., en-US-AriaNeural, en-US-GuyNeural)"
    )
    
    parser.add_argument(
        "--rate",
        default="0%",
        help="Speech rate (e.g., -10%, 0%, +10%)"
    )
    
    parser.add_argument(
        "--pitch",
        default="+1%",
        help="Pitch (e.g., -5%, 0%, +5%)"
    )
    
    args = parser.parse_args()
    
    # Run pipeline
    results = process_ppt_to_voiceover_video(
        pptx_file=args.ppt,
        output_dir=args.output,
        voice_name=args.voice,
        rate_pct=args.rate,
        pitch=args.pitch,
        save_intermediates=False,  # Clean output
        voice_json_path=args.voiceover
    )
    
    print("\n" + "=" * 60)
    print("✅ VIDEO CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"Video: {results.get('output_video')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
