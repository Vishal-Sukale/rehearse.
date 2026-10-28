"""Pure helpers for the coding round: scoring, languages, starter templates and a built-in demo problem."""

# "piston" is the language name used by the code-runner service; None means it runs in the browser.
LANGUAGES = {
    "python": {"label": "Python", "piston": None, "filename": None},
    "c": {"label": "C", "piston": "c", "filename": None},
    "cpp": {"label": "C++", "piston": "c++", "filename": None},
    "java": {"label": "Java", "piston": "java", "filename": "Main.java"},
}

STARTERS = {
    "python": "import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n    # Parse the input, solve the problem, and print the answer.\n\n\nmain()\n",
    "c": "#include <stdio.h>\n\nint main(void) {\n    // Read the input from stdin and print the answer.\n    return 0;\n}\n",
    "cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    // Read the input from cin and print the answer.\n    return 0;\n}\n",
    "java": "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Read the input and print the answer.\n    }\n}\n",
}


def coding_score(passed: int, total: int, quality: int) -> tuple[float, int]:
    """Correctness comes from the tests (70%); code quality, judged by the AI, is 30%.
    Returns (correctness out of 10, score out of 100)."""
    total = max(total, 1)
    passed = max(0, min(passed, total))
    quality = max(0, min(quality, 10))
    correctness = round(10 * passed / total, 1)
    return correctness, round(7 * correctness + 3 * quality)


SAMPLE_PROBLEM = {
    "title": "Two Sum",
    "statement": (
        "Given n integers and a target, print the two indices i and j (0-based, i < j) whose values add up to the "
        "target. Exactly one such pair exists in every test.\n\n"
        "Input format: the first line has n. The second line has n space-separated integers. The third line has the target.\n"
        "Output format: print i and j separated by a space.\n\nAim for O(n) time."
    ),
    "test_inputs": [
        "4\n2 7 11 15\n9\n", "3\n3 2 4\n6\n", "2\n3 3\n6\n",
        "5\n-1 -2 -3 -4 -5\n-8\n", "4\n0 4 3 0\n0\n", "4\n1 5 1 5\n10\n",
    ],
    "reference_solution": (
        "import sys\n\ndata = sys.stdin.read().split()\nn = int(data[0])\nnums = list(map(int, data[1:1 + n]))\n"
        "target = int(data[1 + n])\nseen = {}\nfor j, x in enumerate(nums):\n    if target - x in seen:\n"
        "        print(seen[target - x], j)\n        break\n    seen[x] = j\n"
    ),
    "expected_complexity": "O(n) time, O(n) space",
    "hints": ["A hash map can remember the numbers you have already seen."],
}