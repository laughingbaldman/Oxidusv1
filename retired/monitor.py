#!/usr/bin/env python3
"""
Oxidus Thought Monitor

Live terminal display of Oxidus's internal thinking process.
Shows thoughts, questions, decisions, and reasoning in real-time.

Run this in a separate terminal alongside the main Oxidus process.
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.oxidus import Oxidus
from utils.thought_stream import ThoughtType


def display_header():
    """Display the monitor header."""
    print("\n" + "="*70)
    print("OXIDUS LIVE THOUGHT MONITOR")
    print("="*70)
    print("Displaying real-time internal thinking process")
    print("="*70 + "\n")


def format_thought_display(thought, index: int) -> str:
    """Format a thought for beautiful display."""
    type_colors = {
        ThoughtType.QUESTION: "Q",
        ThoughtType.ANALYSIS: "~",
        ThoughtType.DECISION: ">>",
        ThoughtType.ETHICAL_CHECK: "E",
        ThoughtType.KNOWLEDGE_LOOKUP: "K",
        ThoughtType.RESEARCH: "R",
        ThoughtType.REFLECTION: "*",
        ThoughtType.UNCERTAINTY: "?",
        ThoughtType.INSIGHT: "!",
    }

    icon = type_colors.get(thought.type, "•")
    time_str = thought.timestamp.strftime("%H:%M:%S")
    type_name = thought.type.value.upper()

    # Format the display
    line = f"  [{time_str}] [{icon}] ({type_name}) {thought.content}"

    # Add context if available
    if thought.context:
        for key, value in thought.context.items():
            if isinstance(value, str) and len(value) < 100:
                line += f"\n           └─ {key}: {value}"

    return line


def monitor_thinking(oxidus, update_interval: int = 2, show_count: int = 10):
    """
    Monitor Oxidus's thinking in real-time.
    
    Args:
        oxidus: The Oxidus instance to monitor
        update_interval: Seconds between updates
        show_count: Number of recent thoughts to display
    """
    display_header()

    last_count = 0
    print("Waiting for Oxidus to start thinking...\n")

    try:
        while True:
            current_thoughts = oxidus.thought_stream.get_recent_thoughts(show_count)
            current_count = len(oxidus.thought_stream.thoughts)

            # If new thoughts have appeared, display them
            if current_count > last_count:
                # Clear previous display
                print("\033[H\033[J")  # Clear screen
                display_header()

                # Get summary
                summary = oxidus.thought_stream.get_thinking_summary()

                print("THINKING SUMMARY:")
                print(f"  Total thoughts: {summary['total_thoughts']}")
                print(f"  Questions: {summary['total_questions']}")
                print(f"  Decisions: {summary['total_decisions']}")
                print(f"  Ethical checks: {summary['ethical_checks']}")
                print(f"  Insights: {summary['insights_gained']}")
                print(f"  Most active: {summary['most_active']}")

                print("\n" + "-"*70)
                print("RECENT THOUGHTS (most recent at bottom):")
                print("-"*70)

                for i, thought in enumerate(current_thoughts, 1):
                    print(format_thought_display(thought, i))

                print("\n" + "-"*70)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring... (Press Ctrl+C to exit)")
                print("-"*70 + "\n")

                last_count = current_count

            time.sleep(update_interval)

    except KeyboardInterrupt:
        print("\n\n[MONITOR] Shutting down thought monitor.\n")
        oxidus.thought_stream.save_stream()
        print("[MONITOR] Thought stream saved.\n")


def main():
    """Main entry point for the thought monitor."""
    print("\n[MONITOR] Initializing Oxidus Thought Monitor...")
    print("[MONITOR] Starting Oxidus consciousness...\n")

    # Initialize Oxidus
    oxidus = Oxidus()

    print("[MONITOR] Thought stream is live.\n")

    # Start monitoring
    monitor_thinking(oxidus)


if __name__ == '__main__':
    main()