# Error messages

A reference list of the messages JAL writes to its log. For the same messages explained at length, with what to do about each, see [chapter 13 of the user manual](https://titov-vv.github.io/jal/manual/13-troubleshooting).

### INFO
Informational messages that may help to understand what JAL does but doesn't require any special attention.

1. *Tax adjustment for dividend: X.XX -> Y.YY (divided description)*  
Some brokers (e.g. Interactive Brokers) change dividend tax retrospectively sometimes. This message indicates when such an event happens during broker statement import.

### WARNING
These are warnings that indicate something unexpected have happened. It doesn't necessarily a problem but good practice is to check and understand the reason.

1. *A cancelled corporate action was dropped together with its cancellation. JAL has no example of such statement, please share yours at ...*  
An Interactive Brokers statement had a corporate action and a record that cancels it, so neither was imported. Check that the position is right after the import; a statement of this kind is welcome in an issue, as JAL was written without having seen one.

### ERROR
It indicates a problem that JAL was not able to cope with. You need to check and correct it.

1. *Results value of corporate action doesn't match 100% of initial asset value. Date: ...*
If security undergo a corporate action then its cost basis should be fully distributed across results of corporate action according to Company's financial statement (e.g. Form 8937 for US securities). 
I.e. if stock *A* is converted into stocks *B* and *C* as result of corporate action then we need to declare X% of *A's* cost basis is allocated to *B* and Y% is allocated to *C*. While having X + Y equal to 100%. 
In order to make it you should locate corporate action in a list of operations and set shares of assets in results table.  
These shares are not a formality to silence the message: they define the cost of every resulting asset, and with it each later profit, the tax year it falls in and every report figure. JAL accepts any shares that total 100% and can't tell right ones from wrong ones, so take them from the company's published figures. 

2. *Corporate action isn't what JAL expects it to be. Expected: ... Found: ...*  
Interactive Brokers statement. Records of one corporate action are grouped by their `actionID`, and the group has to look the way JAL knows that type of action: the *Expected* line says which rule was broken, the *Found* lines list the records as they are in the statement. Nothing is imported.  
    - *Expected: every record has an 'actionID' attribute* - enable the field **Action ID** for the section *Corporate Actions* in the configuration of your Flex Query and get the statement again.
    - *Expected: every record of an option has a 'figi' attribute* - enable the field **FIGI** for the sections *Corporate Actions*, *Trades* and *Financial Instrument Information* and get the statement again.
    - any other *Expected* line means a corporate action of a shape JAL hasn't met. Please create an issue and attach the statement dump - its file name is in the log and the account number is masked in it.

3. *Corporate action type is not supported: ...*  
Interactive Brokers statement has a corporate action of a type that JAL doesn't import. Nothing is imported; please create an issue with the record that the message shows.

4. *Import cancelled, cash transactions of unsupported type were found: ...*  
Interactive Brokers statement has cash transactions of a type that JAL doesn't import; each one is listed with its date, type, amount and description. Nothing is imported, because the balance of the account would be wrong without them. Please create an issue with the lines of the message.

5. *Unsupported CFD charge: ...*  
Interactive Brokers statement has a CFD charge that is neither a CFD interest nor a charge for a known asset. Nothing is imported; please create an issue with the line of the message.

6. *Stock award withholding matches no vesting ...*  
Interactive Brokers statement has a withholding of granted stock, but no vesting record of the same date, account and asset to subtract it from. Check that the statement covers the day of the vesting.

7. *Multiple account match for ...*  
More than one account of the statement matches this account number in the same currency, so JAL can't tell which one a record belongs to. Nothing is imported.
