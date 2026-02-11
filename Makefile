render-site:
	cp /Users/poldrack/.cache/academicdb/publications.json .
	uv run quarto render .
	-git add -u
	-git add docs/*
	-git commit -m"updating docs"
	git push origin main
