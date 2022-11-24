render-site:
	quarto render .
	# add rel=me link back into html
	python fix_mastodon_link.py	
	-git add -u
	-git add docs/*
	-git commit -m"updating docs"
	git push origin main
