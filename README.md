Runes to add Hanzi strokes to Anki decks such as https://ankiweb.net/shared/info/132435921.

```
$ python3 anki-hsk-strokes.py
```

You should back up your database before doing this.

You'll also want the SVGs from https://github.com/skishore/makemeahanzi.

```
cd svgs-still
find . -name '*-still.svg' | while read -r file; do
  code=$(echo "$file" | sed -E 's|.*/([0-9]+)-.*|\1|')
  char=$(printf "\\U$(printf '%08x' "$code")")
  cp $code-still.svg ~/.local/share/Anki2/User\ 1/collection.media/$char.svg
done
```

