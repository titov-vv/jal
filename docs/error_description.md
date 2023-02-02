# Error messages

### INFO
Informational messages that may help to understand what JAL does but doesn't require any special attention.

1. *Tax adjustment for dividend: X.XX -> Y.YY (divided description)*  
Some brokers (e.g. Interactive Brokers) change dividend tax retrospectively sometimes. This message indicates when such an event happens during broker statement import.

### WARNING
These are warnings that indicate something unexpected have happened. It doesn't necessarily a problem but good practice is to check and understand the reason.

### ERROR
It indicates a problem that JAL was not able to cope with. You need to check and correct it.

1. *Results value of corporate action doesn't match 100% of initial asset value. Date: ...*
If security undergo a corporate action then its cost basis should be fully distributed across results of corporate action according to Company's financial statement (e.g. Form 8937 for US securities). 
I.e. if stock *A* is converted into stocks *B* and *C* as result of corporate action then we need to declare X% of *A's* cost basis is allocated to *B* and Y% is allocated to *C*. While having X + Y equal to 100%. 
In order to make it you should locate corporate action in a list of operations and set shares of assets in results table. 
