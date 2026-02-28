import re

def main():
    with open('main.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Replace MY_* definitions with tuples
    old_defs = """# Material You Dark Theme Colors
MY_BG = "#1A1C1E"              # Surface
MY_SURFACE = "#202529"         # Surface Container Low
MY_SURFACE_HIGH = "#2A3136"    # Surface Container High
MY_PRIMARY = "#A1C9FF"         # Primary (Soft Blue)
MY_ON_PRIMARY = "#00325A"      # On Primary (Dark text)
MY_SECONDARY = "#BCC7DB"       # Secondary
MY_ERROR = "#FFB4AB"           # Error red
MY_SUCCESS = "#81C784"         # Success green
MY_TEXT = "#E2E2E6"            # On Surface
MY_TEXT_MUTED = "#8C9199"      # On Surface Variant"""

    new_defs = """# Material You Colors (Light, Dark)
MY_BG = ("#FDFBFF", "#1A1C1E")
MY_SURFACE = ("#F2F4F9", "#202529")
MY_SURFACE_HIGH = ("#E1E2E8", "#2A3136")
MY_PRIMARY = ("#0061A4", "#A1C9FF")
MY_ON_PRIMARY = ("#FFFFFF", "#00325A")
MY_SECONDARY = ("#535F70", "#BCC7DB")
MY_ERROR = ("#BA1A1A", "#FFB4AB")
MY_SUCCESS = ("#106D34", "#81C784")
MY_TEXT = ("#1A1C1E", "#E2E2E6")
MY_TEXT_MUTED = ("#73777F", "#8C9199")"""

    text = text.replace(old_defs, new_defs)

    # 2. Patch Matplotlib kwargs
    def sub_mpl(match):
        kwarg = match.group(1)
        val = match.group(2)
        return f'{kwarg}={val}[1]'

    # Catch matplotlib kwargs strictly using these names: facecolor, color, edgecolor, labelcolor
    # ensuring they don't already end in [1]
    text = re.sub(r'\b(facecolor|color|edgecolor|labelcolor)=(MY_[A-Z_]+)(?!\[)', sub_mpl, text)

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    main()
