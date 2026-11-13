# Local LaTeX Compilation — MacTeX Setup Guide

This guide lets you compile the thesis (or individual chapters) on your Mac without Overleaf.

---

## 1. Install MacTeX

### Option A — Full MacTeX (~4.3 GB, recommended)

Includes everything: compilers, BibTeX/Biber, GUI tools, all packages pre-installed.

1. Go to **https://tug.org/mactex/**
2. Click **MacTeX Download** → download `MacTeX.pkg`
3. Double-click the `.pkg` file and follow the installer
4. After installation, open a new Terminal window and verify:
   ```
   pdflatex --version
   biber --version
   latexmk --version
   ```
   All three should print version numbers.

### Option B — BasicTeX (~100 MB, minimal)

Smaller download, but you must install missing packages manually via `tlmgr`.

1. Go to **https://tug.org/mactex/mactex-download.html** → scroll to **BasicTeX**
2. Download and install `BasicTeX.pkg`
3. Install the packages this thesis needs:
   ```
   sudo tlmgr update --self
   sudo tlmgr install biblatex biber latexmk booktabs subfig \
       setspace fullpage microtype listings xcolor algorithm \
       algorithmicx babel-english lm
   ```

---

## 2. Compile a Single Chapter (Overleaf workaround)

The `temp_run/` folder contains one standalone `.tex` file per chapter. Each file is self-contained and compiles independently — no Overleaf limit issues.

```bash
cd /path/to/bachelor_thesis/temp_run

# Compile with latexmk (handles biber automatically — recommended)
latexmk -pdf ch3_methodology.tex

# Or any other chapter:
latexmk -pdf ch1_introduction.tex
latexmk -pdf ch2_litrev.tex
latexmk -pdf ch4_implementation.tex
latexmk -pdf ch5_results.tex
latexmk -pdf ch6_discussion.tex
latexmk -pdf ch7_conclusion.tex
```

The PDF will appear in the same `temp_run/` folder.

### Manual 4-step sequence (if latexmk is unavailable)

```bash
pdflatex ch3_methodology.tex
biber    ch3_methodology
pdflatex ch3_methodology.tex
pdflatex ch3_methodology.tex
```

---

## 3. Compile the Full Thesis

```bash
cd /path/to/bachelor_thesis

latexmk -pdf main.tex
```

Output: `main.pdf` in the `bachelor_thesis/` folder.

To clean auxiliary files afterwards:

```bash
latexmk -c
```

---

## 4. Optional: VS Code + LaTeX Workshop (GUI experience)

A comfortable editor setup that shows a live PDF preview alongside the source.

1. Install **VS Code** from https://code.visualstudio.com/
2. Open VS Code → Extensions (⇧⌘X) → search **LaTeX Workshop** → Install
3. Open the `bachelor_thesis/` folder in VS Code
4. Open `main.tex` (or any `temp_run/chX_*.tex`)
5. Click the green **▶ Build LaTeX project** button (top-right) or press `⌘⇧B`
6. The PDF preview opens automatically on the right side

LaTeX Workshop uses `latexmk` by default and handles the biber pass automatically.

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: pdflatex` | Restart Terminal after installing MacTeX, or run `/Library/TeX/texbin/pdflatex` |
| Missing package error | Run `sudo tlmgr install <packagename>` |
| Bibliography not showing | Run biber manually: `biber main` then pdflatex twice |
| Figures not found | Run latexmk from inside `temp_run/`, not from parent folder |
