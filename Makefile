.PHONY: test test-unit test-integration test-e2e build publish publish-pip clean

test:
	python -m pytest tests/ -v

test-unit:
	python -m pytest tests/ -v -m "not integration"

test-integration:
	python -m pytest tests/ -v -m integration

test-e2e:
	python -m pytest tests/test_e2e.py -v

build: clean
	uv build

publish: publish-pip

publish-pip: build
	uvx twine upload dist/*

clean:
	rm -rf dist/
