# VHS tape — records this directory's demo.sh into demo.gif.
# Regenerate with: cd examples/parent-child-handoff && vhs demo.tape
# (requires https://github.com/charmbracelet/vhs: brew install vhs)

Output demo.gif

Require downbeat

Set Shell "zsh"
Set FontFamily "Menlo"
Set FontSize 20
Set Width 1200
Set Height 650
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 40ms

Type "./demo.sh"
Enter
Sleep 5s
