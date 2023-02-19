r"""
A Database of Cyclic Voltammograms.

EXAMPLES:

Create a database from local data packages in the `data/` directory::

    >>> from echemdb.local import collect_datapackages
    >>> database = Database(collect_datapackages('data/'))

Create a database from the data packages published in the echemdb::

    >>> database = Database()  # doctest: +REMOTE_DATA

Search the database for a single publication::

    >>> database.filter(lambda entry: entry.source.url == 'https://doi.org/10.1039/C0CP01001D')  # doctest: +REMOTE_DATA
    [Entry('alves_2011_electrochemistry_6010_f1a_solid'), ...

"""
# ********************************************************************
#  This file is part of echemdb.
#
#        Copyright (C) 2021-2022 Albert Engstfeld
#        Copyright (C) 2021      Johannes Hermann
#        Copyright (C) 2021-2022 Julian Rüth
#        Copyright (C) 2021      Nicolas Hörmann
#
#  echemdb is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  echemdb is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with echemdb. If not, see <https://www.gnu.org/licenses/>.
# ********************************************************************
import logging

logger = logging.getLogger("echemdb")


class Database:
    r"""
    A collection of [data packages](https://github.com/frictionlessdata/datapackage-py).

    Essentially this is just a list of data packages with some additional
    convenience wrap for use in the echemdb.

    EXAMPLES:

    An empty database::

        >>> database = Database([])
        >>> len(database)
        0

    """

    def __init__(self, data_packages=None, bibliography=None):
        if data_packages is None:
            import os.path

            import echemdb.remote

            data_packages = echemdb.remote.collect_datapackages(
                os.path.join("website-gh-pages", "data", "generated", "svgdigitizer")
            )

            if bibliography is None:
                bibliography = echemdb.remote.collect_bibliography(
                    os.path.join("website-gh-pages", "data", "generated")
                )

        if bibliography is None:
            bibliography = []

        from collections.abc import Iterable

        if isinstance(bibliography, Iterable):
            from pybtex.database import BibliographyData

            bibliography = BibliographyData(
                entries={entry.key: entry for entry in bibliography}
            )

        self._packages = data_packages
        self._bibliography = bibliography

    @classmethod
    def create_example(cls):
        r"""
        Return a sample database for use in automated tests.

        EXAMPLES::

            >>> Database.create_example()
            [Entry('alves_2011_electrochemistry_6010_f1a_solid'), Entry('engstfeld_2018_polycrystalline_17743_f4b_1')]

        """
        from echemdb.cv.entry import Entry

        entries = Entry.create_examples(
            "alves_2011_electrochemistry_6010"
        ) + Entry.create_examples("engstfeld_2018_polycrystalline_17743")

        return Database(
            [entry.package for entry in entries],
            [entry.bibliography for entry in entries],
        )

    @property
    def bibliography(self):
        r"""
        Return a pybtex database of all bibtex bibliography files.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> database.bibliography
            BibliographyData(
              entries=OrderedCaseInsensitiveDict([
                ('alves_2011_electrochemistry_6010', Entry('article',
                ...
                ('engstfeld_2018_polycrystalline_17743', Entry('article',
                ...

        """
        from pybtex.database import BibliographyData

        return BibliographyData(
            {
                entry.bibliography.key: entry.bibliography
                for entry in self
                if entry.bibliography
            }
        )

    def filter(self, predicate):
        r"""
        Return the subset of the database that satisfies predicate.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> database.filter(lambda entry: entry.source.url == 'https://doi.org/10.1039/C0CP01001D')
            [Entry('alves_2011_electrochemistry_6010_f1a_solid')]


        The filter predicate can use properties that are not present on all
        entries in the database. If a property is missing the element is
        removed from the database::

            >>> database.filter(lambda entry: entry.non.existant.property)
            []

        """

        def catching_predicate(entry):
            try:
                return predicate(entry)
            except (KeyError, AttributeError) as e:
                logger.debug(f"Filter removed entry {entry} due to error: {e}")
                return False

        return Database(
            data_packages=[
                entry.package for entry in self if catching_predicate(entry)
            ],
            bibliography=self._bibliography,
        )

    def __iter__(self):
        r"""
        Return an iterator over the entries in this database.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> next(iter(database))
            Entry('alves_2011_electrochemistry_6010_f1a_solid')

        """
        from echemdb.cv.entry import Entry

        def get_bibliography(package):
            bib = Entry(package, bibliography=None).source.citation_key
            return self._bibliography.entries.get(bib, None)

        # Return the entries sorted by their identifier. There's a small cost
        # associated with the sorting but we do not expect to be managing
        # millions of identifiers and having them show in sorted order is very
        # convenient, e.g., when doctesting.
        return iter(
            [
                Entry(package, bibliography=get_bibliography(package))
                for package in sorted(self._packages, key=lambda p: p.resources[0].name)
            ]
        )

    def __len__(self):
        r"""
        Return the number of entries in this database.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> len(database)
            2

        """
        return len(self._packages)

    def __repr__(self):
        r"""
        Return a printable representation of this database.

        EXAMPLES::

            >>> Database([])
            []

        """
        return repr(list(self))

    def __getitem__(self, identifier):
        r"""
        Return the entry with this identifier.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> database['alves_2011_electrochemistry_6010_f1a_solid']
            Entry('alves_2011_electrochemistry_6010_f1a_solid')

            >>> database['invalid_key']
            Traceback (most recent call last):
            ...
            KeyError: "No database entry with identifier 'invalid_key'."

        """
        entries = [entry for entry in self if entry.identifier == identifier]

        if len(entries) == 0:
            raise KeyError(f"No database entry with identifier '{identifier}'.")
        if len(entries) > 1:
            raise KeyError(
                f"The database has more than one entry with identifier '{identifier}'."
            )
        return entries[0]

    def materials(self):
        r"""
        Return the substrate materials in the database.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> database.materials()
            ['Ru', 'Cu']

        """
        import pandas as pd

        return list(
            pd.unique(
                pd.Series(
                    [
                        entry.system.electrodes.working_electrode.material
                        for entry in self
                    ]
                )
            )
        )

    def describe(self):
        r"""
        Returns some statistics about the database.

        EXAMPLES::

            >>> database = Database.create_example()
            >>> database.describe() # doctest: +NORMALIZE_WHITESPACE
            {'number of references': 2,
            'number of entries': 2,
            'materials': ['Ru', 'Cu']}

        """
        return {
            "number of references": len(self.bibliography.entries),
            "number of entries": len(self),
            "materials": self.materials(),
        }

    def plot(self, x_label="E", y_label="j", force_plot=False):
        r"""
        Return a plot with all entries of the database.
        The default plot is a cyclic voltammogram ('j vs E').
        When `j` is not defined `I` is used instead.

        EXAMPLES::

            >>> entry = Entry.create_examples()[0]
            >>> entry.plot()
            Figure(...)

        The plot can also be returned with custom axis units available in the resource::

            >>> entry.plot(x_label='t', y_label='E')
            Figure(...)

        The plot with axis units of the original figure can be obtained by first rescaling the entry::

            >>> rescaled_entry = entry.rescale('original')
            >>> rescaled_entry.plot()
            Figure(...)

        """
        if len(self) > 10:
            if force_plot == False:
                raise Exception('The database has more than 10 entries. To plot all entries anyway, set `force_plot` to `True`')

        import plotly.graph_objects

        fig = plotly.graph_objects.Figure()

        # TODO:: Rescale database. Implement `database.rescale` function
        # Add units as a parameter to the function for rescaling
        # Implement rescaling different voltage axis
        # Verify that all x and y columen names are identical, i.e., j and I can not be plotted in the same figure.
        
        for entry in self:

            x_label = entry._normalize_field_name(x_label)
            y_label = entry._normalize_field_name(y_label)

            fig.add_trace(
                plotly.graph_objects.Scatter(
                    x=self.df[x_label],
                    y=self.df[y_label],
                    mode="lines",
                    name=f"Fig. {self.source.figure}: {self.source.curve}",
                )
            )

        # get a reference electrode from any entry. This should be fine once the database is normalized to a specific reference.
        def reference(label):
            if label == "E":
                return f" vs. {self.package.get_resource('echemdb').schema.get_field(label)['reference']}"

            return ""

        def axis_label(label):
            return f"{label} [{self.field_unit(label)}{reference(label)}]"

        fig.update_layout(
            template="simple_white",
            showlegend=True,
            autosize=True,
            width=600,
            height=400,
            margin=dict(l=70, r=70, b=70, t=70, pad=7),
            xaxis_title=axis_label(x_label),
            yaxis_title=axis_label(y_label),
        )

        fig.update_xaxes(showline=True, mirror=True)
        fig.update_yaxes(showline=True, mirror=True)

        return fig