render-site:
	quarto render .
	git commit -a -m"updating docs"
	git push origin main
