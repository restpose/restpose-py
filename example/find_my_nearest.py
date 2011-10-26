#!/usr/bin/env python
# -*- coding: utf-8 -
#
# This file is part of the restpose python module, released under the MIT
# license.  See the COPYING file for more information.

"""
An example of implemnting a search for the nearest item.

This example requires the "restpose" and "flask" python modules to be
installed.

To load some sample data in::

  python find_my_nearest.py csv find_my_nearest_data.csv

To perform a search::

  python find_my_nearest.py search lat=51.5357 lon=-0.1557318936202792 type=zoo type=tv

To start the server running:

  python serve  # add a "debug" parameter to start in debug mode.

When the server is running, go to http://localhost:5000/ to get a form for
entering some example searches, and go to http://localhost:5000/search to get
the search results (as JSON).  Note that the form is limited in the types of
search it can create - any label fields can be searched, and can be searched
for multiple values by supplying them multiple times.

Results are returned in order of distance from the supplied point, closest
first, filtered to match the supplied labels.

"""

import csv
import flask
import json
import restpose
import sys

class Context(object):

    def __init__(self):
        self.collection = restpose.Server().collection('find_my_nearest')
        self.places = self.collection.doc_type('place')

    def add_item(self, id, name, description, url, postcode, geolocation, fbid,
                 labels):
        """Add an item to the collection (or update an old item).

        :param id: A unique identifier for the item (an arbitrary string)
        :param name: A name for the item (plain text, no length limit).
        :param description: A description for the item (plain text, no length
               limit).
        :param postcode: A postcode for the item.
        :param geolocation: A [latitude, longitude] pair for the item.
        :param fbid: An identifier for the item on facebook.
        :param labels: A dictionary of extra labels to associate with the item.

        """
        fields = dict(id=id, name_text=name, description_text=description,
                      url=url, postcode_tag=postcode, fbid_tag=fbid)
        fields['lonlat'] = dict(lat=geolocation[0], lon=geolocation[1])
        for k, v in labels.iteritems():
            fields[k + 'label_tag'] = v

        self.places.add_doc(fields)

    def import_from_rows(self, rows):
        """Import some data from an iterator over rows.

        This can be used, for example, to import data from CSV.
        Each row should contain the following:

         - ID: the identifier for the item (an arbitrary string).
         - name: A name for the item (plain text, no length limit).
         - description: A description for the item (plain text, no length
           limit).
         - postcode: A postcode for the item.
         - latitude: The latitude of the item (as a decimal).
         - longitude: The longitude of the item (as a decimal).
         - fbid: An identifier for the item on facebook (an arbitrary string).
         - labels: A semi-colon separated list of labels for the item.  Each
           label has a category and a value, separated by '='.  For example,
           "activity=tour;activity=feeding".  Each category can appear multiple
           times, or not at all.

        Returns a list of any errors which occurred while importing.

        """
        for row in rows:
            (id, name, description, url, postcode, latitude, longitude, fbid,
             labels) = row
            latitude = float(latitude)
            longitude = float(longitude)

            # unpack the labels
            unpacked_labels = {}
            for label in labels.split(';'):
                cat, val = label.split('=')
                unpacked_labels.setdefault(cat.strip(), []).append(val.strip())

            self.add_item(id, name, description, url, postcode, [latitude,
                          longitude], fbid, unpacked_labels)
        return self.collection.checkpoint().wait().errors

    def clear(self):
        """Clear the entire collection.

        """
        self.collection.delete()

    def search(self, **kwargs):
        """Perform a search.

        kwargs contains the parameters to search for; the values should always
        be lists of values to search for.

        """
        # Ensure that values are lists
        for k, v in kwargs.items():
            if (not hasattr(v, '__iter__') and
                not isinstance(v, basestring)):
                v = [v]
                kwargs[k] = v
            if len(v) == 0:
                del kwargs[k]

        # Parse lat, lon parameters
        lat = filter(lambda x: x != '', kwargs.get('lat', []))
        lon = filter(lambda x: x != '', kwargs.get('lon', []))
        if len(lat) != 0 or len(lon) != 0:
            if len(lat) == 0 or len(lon) == 0:
                raise ValueError('Must supply both lat and lon parameters '
                                 'if either supplied')
            if len(lat) != 1:
                raise ValueError('Must supply exactly 1 latitude parameter')
            if len(lon) != 1:
                raise ValueError('Must supply exactly 1 longitude parameter')
            lat = float(lat[0])
            lon = float(lon[0])
            q = self.places.field('lonlat').distscore(dict(lat=lat, lon=lon))
        else:
            q = self.places.all()

        # Handle any label filters
        for k, v in kwargs.items():
            if k in ('lat', 'lon', 'search'):
                continue
            if len(v) == 0 or v[0] == '':
                continue
            field = self.places.field(k + 'label_tag')
            q = q.filter(field.is_in(v))
        print q._build_search()

        # Tidy up the result structures.
        results = []
        for item in q:
            data = {}
            for k, v in item.data.items():
                if k.endswith('label_tag'):
                    k = k[:-9]
                    # Labels can occur multiple times, so leave their value as
                    # a list.
                elif k == 'type':
                    # Don't want to return the type of the item
                    continue
                else:
                    if k.endswith('_tag'):
                        k = k[:-4]
                    if k.endswith('_text'):
                        k = k[:-5]
                    assert len(v) == 1
                    v = v[0]
                data[k] = v
            results.append(data)
        return results

def do_cmd(cmd, args):
    """Some command line actions.

     - clear: Clear the database
     - csv <filename>: Load some data from a CSV file.
     - search <param=val> <param=val>: Perform a search, using specified
       parameters.

    """
    if cmd == 'clear':
        context = Context()
        context.clear()

    elif cmd == 'csv':
        context = Context()
        filename = args[0]
        with open(filename, "r") as fd:
            reader = csv.reader(fd, dialect='excel')
            errors = context.import_from_rows(reader)
            if errors:
                print "Errors while indexing", errors
            print "Collection now contains %d places" % (
                context.places.all().matches_estimated
            )

    elif cmd == 'search':
        context = Context()
        params = {}
        for arg in args:
            k, v = arg.split('=')
            params.setdefault(k.strip(), []).append(v.strip())
        print context.search(**params)

    elif cmd == 'serve':
        context = Context()
        app = flask.Flask('find_my_nearest')

        if len(args) > 0 and args[0] == 'debug':
            app.debug = True

        @app.route('/search')
        def search():
            kwargs = dict(flask.request.args.lists())
            try:
                return flask.jsonify(dict(results=context.search(**kwargs)))
            except ValueError, e:
                return flask.jsonify(dict(error=str(e)))

        @app.route('/')
        def top():
            return '''<?doctype html><html>
            <head><title>Search</title></head><body>
            <form action="/search" method="GET">
              <label for="lat">Latitude:</label>
              <input type="text" id="lat" name="lat" placeholder="Latitude">
              <br>

              <label for="lon">Longitude:</label>
              <input type="text" id="lon" name="lon" placeholder="Longitude">
              <br>

              Some example labels:<br>
              <label for="type">Type:</label>
              <input type="text" id="type" name="type" placeholder="Type; eg. tv">
              <br>

              <label for="activity">Activity:</label>
              <input type="text" id="activity" name="activity" placeholder="Activity; eg. tour">
              <br>

              <input type="submit" name="search" value="Search">
            </form></body></html>
            '''

        if app.debug:
            app.run()
        else:
            app.run(host='0.0.0.0')

    else:
        print "Unknown command"


if __name__ == '__main__':
    do_cmd(sys.argv[1], sys.argv[2:])
