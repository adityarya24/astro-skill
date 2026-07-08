# Swiss Ephemeris data files

These `.se1` files are the Swiss Ephemeris data used for high-precision
sidereal positions:

- `sepl_18.se1` — planets, ~1800–2399 CE
- `semo_18.se1` — Moon, ~1800–2399 CE

Together they cover the full range of realistic birth dates. When present, the
calculators use the precise Swiss Ephemeris (`SWIEPH`); without them, swisseph
falls back to the built-in Moshier model, and `calculation.ephemeris` in the
output reports `"moshier"` instead of `"swieph"`.

## Source

Astrodienst AG Swiss Ephemeris distribution
(<https://www.astro.com/ftp/swisseph/ephe/>, mirrored at
<https://github.com/aloistr/swisseph>).

## License

The Swiss Ephemeris (and these data files) are distributed by Astrodienst under
the **GNU Affero General Public License (AGPL-3.0)** or, alternatively, a paid
commercial license. This project already depends on `pyswisseph`, which carries
the same terms, so bundling the data is consistent with that obligation.

Anyone redistributing this repository or the Docker image must comply with the
Swiss Ephemeris license. If you intend to ship a closed-source commercial
product on top of this engine, obtain a Swiss Ephemeris commercial license from
Astrodienst. See <https://www.astro.com/swisseph/swephinfo_e.htm>.
