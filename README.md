# Portfolio rebalance

`test_rebalance.py` checks the table printed by `rebalance.py`. It does not store the share counts. It reads them from that run.

With no pipe, the tests run the default account ABC ($100,000):

```powershell
py test_rebalance.py
```

Any other account is checked by piping the program output. Pass the account total and a CSV file with columns `name,target_percent,current_percent,price`. The table can hold from 1 to 10 securities.

```powershell
py rebalance.py 100000 example_book.csv | py test_rebalance.py
```

Assumptions checked by the tests:

- Share counts are printed with 6 decimal places.
- Buy cash rounds up to the cent. Sell cash rounds down to the cent.
- An exact cent stays as it is. A fractional cent rounds up on a buy and down on a sell.
- The printed table carries the account total, target percent, current percent, and price.


