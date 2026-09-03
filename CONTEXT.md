# faðir

faðir is a hosted service for private investment portfolios. It keeps a person's sign-in identity separate from each Portfolio.

## Language

**User**:
A person who can sign in to faðir and control one Workspace. A User can attach more than one Login Identity.
_Avoid_: Account, profile

**Workspace**:
A stable, private container for one or more Portfolios. It belongs to one User or remains anonymous as a Guest Workspace.
_Avoid_: User, Portfolio, database

**Portfolio**:
A named, private set of investment instruments, transactions, and derived values inside one Workspace. It has one Base Currency and does not support team access.
_Avoid_: Database, account

**Guest Workspace**:
A Workspace that has no User and depends on its browser session for access. It expires after 90 days without access.
_Avoid_: Guest account, temporary database, User

**Login Identity**:
A verified sign-in method attached to one User. A User can attach both Google and an email magic link.
_Avoid_: Login account

**User Session**:
One browser's revocable access to a User. It expires after 30 days without activity.
_Avoid_: Login Identity, Guest Workspace

**Operator**:
The person who maintains service health, quotas, and failures without normal access to Portfolio content.
_Avoid_: Portfolio owner, User

**Instrument**:
A market security that passed provider validation and can appear in a Portfolio.
_Avoid_: Stock Group, position

**Base Currency**:
The changeable currency that a Portfolio uses for headline values and return views. A Base Currency change does not change original transactions.
_Avoid_: Native currency, trading currency

**Tax Jurisdiction**:
The country whose tax rules and official currency govern a Tax Estimate.
_Avoid_: Base Currency, market country

**Tax Profile**:
A User-level record for one Tax Jurisdiction and tax year. It lets all of the User's Portfolios contribute to one Tax Estimate.
_Avoid_: Portfolio setting, tax return

**Tax Estimate**:
A non-advisory calculation under one Tax Profile. It uses the jurisdiction currency, which can differ from the Portfolio Base Currency.
_Avoid_: Tax return, tax advice

**Default Portfolio**:
The first Portfolio created for a Workspace after its first saved transaction. Its initial display name is Ana Portföy.
_Avoid_: Shared portfolio, global portfolio

**Claim**:
The transition that attaches a Guest Workspace to a new User without a data move.
_Avoid_: Registration, Merge

**Portfolio Transfer**:
An explicit choice that moves Guest Workspace Portfolios into a current User's Workspace as separate Portfolios.
_Avoid_: Automatic Merge, overwrite

**Portfolio Merge**:
A User-confirmed move of guest transactions into one selected User Portfolio. Possible duplicates require a keep-or-skip choice before the move.
_Avoid_: Automatic Merge, Portfolio Transfer

**Stock Group**:
All transactions for one instrument within one Portfolio.
_Avoid_: Portfolio, account

**Average Purchase Price**:
The quantity-weighted native-currency cost of all purchases in a Stock Group. It includes purchase fees and excludes sales. A fully sold group keeps this value.
_Avoid_: Current price, FIFO cost, break-even price

**Fee Currency**:
The currency of a transaction fee. The service converts it on the transaction date when it differs from the transaction currency.
_Avoid_: Base Currency, price currency
