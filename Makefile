render-site:
	quarto render .
	-git add -u
	-git add docs/*
	-git commit -m"updating docs"
	git push origin main
