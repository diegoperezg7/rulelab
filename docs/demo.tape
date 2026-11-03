# Renders docs/assets/demo.gif with https://github.com/charmbracelet/vhs
Output docs/assets/demo.gif
Set Shell "bash"
Set FontSize 15
Set Width 1200
Set Height 640
Set Padding 24
Set Theme { "name": "rulelab", "black": "#111116", "red": "#f66d67", "green": "#5fd37f", "yellow": "#f7b83d", "blue": "#a0a2ff", "magenta": "#b999fb", "cyan": "#a0a2ff", "white": "#f4f5f8", "brightBlack": "#5c5d66", "brightRed": "#f66d67", "brightGreen": "#5fd37f", "brightYellow": "#f7b83d", "brightBlue": "#a0a2ff", "brightMagenta": "#b999fb", "brightCyan": "#a0a2ff", "brightWhite": "#ffffff", "background": "#000000", "foreground": "#f4f5f8", "selection": "#28282e", "cursor": "#a0a2ff" }
Hide
Type "export COLUMNS=110 PS1='$ '" Enter
Type "clear" Enter
Show
Type "rulelab split examples/demo/AGENTS.md" Sleep 400ms Enter
Sleep 2.5s
Type "rulelab demo --out /tmp/rulelab-demo.html" Sleep 400ms Enter
Sleep 7s
