# Banker OS origination refresh

Monthly pipeline that rebuilds the sell-side origination universe in James Oyuke's private Banker OS page.

Sources: CQC register (monthly), Ofsted early years (quarterly), Ofsted children's social care and ownership (annual),
Companies House basic company data, PSC snapshot and 12 months of iXBRL accounts, plus the Companies House API
for directors and unmatched owners.

Run: `WORK=/path/to/workdir CH_API_KEY=... bash run.sh` (40–75 minutes). Output: `$WORK/plan.json` and `$WORK/out/`,
which the scheduled task writes into the page's private store (collection `udir`), then switches `udir/index`.

The API key is never stored in this repository.
