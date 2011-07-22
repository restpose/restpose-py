# Run all tests

nosetests &&
(cd docs && make doctest)
