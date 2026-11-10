# EVDS discovery failed

```
Traceback (most recent call last):
  File "/home/runner/work/turkiye-trade-macro/turkiye-trade-macro/etl/discover.py", line 47, in <module>
    main()
  File "/home/runner/work/turkiye-trade-macro/turkiye-trade-macro/etl/discover.py", line 29, in main
    hit = groups[groups.apply(lambda r: matches(r, words), axis=1)]
                 ^^^^^^^^^^^^
AttributeError: 'list' object has no attribute 'apply'

```
