#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Frederic Rodrigo 2013                                      ##
##                                                                       ##
## This program is free software: you can redistribute it and/or modify  ##
## it under the terms of the GNU General Public License as published by  ##
## the Free Software Foundation, either version 3 of the License, or     ##
## (at your option) any later version.                                   ##
##                                                                       ##
## This program is distributed in the hope that it will be useful,       ##
## but WITHOUT ANY WARRANTY; without even the implied warranty of        ##
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         ##
## GNU General Public License for more details.                          ##
##                                                                       ##
## You should have received a copy of the GNU General Public License     ##
## along with this program.  If not, see <http://www.gnu.org/licenses/>. ##
##                                                                       ##
###########################################################################

import bz2

from . import OsmSax
from .IssuesFile_PolygonFilter import PolygonFilter


class IssuesFileOsmose:

    def __init__(self, dst, version = None, polygon_id = None):
        self.dst = dst
        self.version = version
        self.filter = None
        if polygon_id:
            try:
                self.filter = PolygonFilter(polygon_id)
            except Exception as e:
                print(e)
                pass

    def begin(self):
        if isinstance(self.dst, str):
            if self.dst.endswith(".bz2"):
                output = bz2.BZ2File(self.dst, "w")
            else:
                output = open(self.dst, "w")
        else:
            output = self.dst
        self.outxml = OsmSax.OsmSaxWriter(output, "UTF-8")
        self.outxml.startDocument()
        self.outxml.startElement("analysers", {})
        self.geom_type_renderer = {"node": self.outxml.NodeCreate, "way": self.outxml.WayCreate, "relation": self.outxml.RelationCreate, "position": self.position}

    def end(self):
        self.outxml.endElement("analysers")
        self.outxml.endDocument()
        del self.outxml

    def analyser(self, timestamp, analyser_version, change=False):
        self.mode = "analyserChange" if change else "analyser"
        attrs = {}
        attrs["timestamp"] = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        attrs["analyser_version"] = str(analyser_version)
        if self.version is not None:
            attrs["version"] = self.version
        self.outxml.startElement(self.mode, attrs)

    def analyser_end(self):
        self.outxml.endElement(self.mode)

    def classs(self, id, item, level, tags, title, detail = None, fix = None, trap = None, example = None, source = None, resource = None):
        options = {
            'id': str(id),
            'item': str(item),
        }
        if source:
            options['source'] = str(source)
        if resource:
            options['resource'] = str(resource)
        if level:
            options['level'] = str(level)
        if tags:
            options['tag'] = ','.join(tags)
        self.outxml.startElement('class', options)
        for (key, value) in [
            ('classtext', title),
            ('detail', detail),
            ('fix', fix),
            ('trap', trap),
            ('example', example),
        ]:
            if value:
                for lang in sorted(value.keys()):
                    self.outxml.Element(key, {
                        'lang': lang,
                        'title': value[lang]
                    })
        self.outxml.endElement('class')

    def error(self, classs, subclass, text, res, fixType, fix, geom, allow_override=False):
        if self.filter and not self.filter.apply(classs, subclass, geom):
            return

        if subclass is not None:
            self.outxml.startElement("error", {"class":str(classs), "subclass":str(subclass)})
        else:
            self.outxml.startElement("error", {"class":str(classs)})
        for type in geom:
            for g in geom[type]:
                self.geom_type_renderer[type](g)
        if text:
            for lang in text:
                self.outxml.Element("text", {"lang":lang, "value":text[lang]})
        if fix:
            fix = self.fixdiff(fix)
            if not allow_override:
                fix = self.filterfix(res, fixType, fix, geom)
            self.dumpxmlfix(res, fixType, fix)
        self.outxml.endElement("error")

    def position(self, args):
        self.outxml.Element("location", {"lat":str(args["lat"]), "lon":str(args["lon"])})

    def delete(self, t, id):
        self.outxml.Element("delete", {"type": t, "id": str(id)})

    FixTable = {'~':'modify', '+':'create', '-':'delete'}

    def fixdiff(self, fixes):
        """
        Normalise fix in e
        Normal form is [[{'+':{'k1':'v1', 'k2', 'v2'}, '-':{'k3':'v3'}, '~':{'k4','v4'}}, {...}]]
        Array of alternative ways to fix -> Array of fix for objects part of error -> Dict for diff actions -> Dict for tags
        """
        if not isinstance(fixes, list):
            fixes = [[fixes]]
        elif not isinstance(fixes[0], list):
            # Default one level array is different way of fix
            fixes = list(map(lambda x: [x], fixes))
        return list(map(lambda fix:
            list(map(lambda f:
                None if f is None else (f if '~' in f or '-' in f or '+' in f else {'~': f}),
                fix)),
            fixes))

    def filterfix(self, res, fixesType, fixes, geom):
        ret_fixes = []
        for fix in fixes:
            i = 0
            for f in fix:
                if f is not None and i < len(fixesType):
                    osm_obj = next((x for x in geom[fixesType[i]] if x['id'] == res[i]), None)
                    if osm_obj:
                        fix_tags = f['+'].keys() if '+' in f else []
                        if len(set(osm_obj['tag'].keys()).intersection(fix_tags)) > 0:
                            # Fix try to override existing tag in object, drop the fix
                            i = 0
                            break
                i += 1
            if i > 0:
                ret_fixes.append(fix)
        return ret_fixes

    def dumpxmlfix(self, res, fixesType, fixes):
        self.outxml.startElement("fixes", {})
        for fix in fixes:
            self.outxml.startElement("fix", {})
            i = 0
            for f in fix:
                if f is not None and i < len(fixesType):
                    type = fixesType[i]
                    if type:
                        self.outxml.startElement(type, {'id': str(res[i])})
                        for opp, tags in f.items():
                            for k in tags:
                                if opp in '~+':
                                    self.outxml.Element('tag', {'action': self.FixTable[opp], 'k': k, 'v': tags[k]})
                                else:
                                    self.outxml.Element('tag', {'action': self.FixTable[opp], 'k': k})
                        self.outxml.endElement(type)
                i += 1
            self.outxml.endElement('fix')
        self.outxml.endElement('fixes')

################################################################################
import unittest

class Test(unittest.TestCase):
    def setUp(self):
        self.a = IssuesFileOsmose(None)

    def check(self, b, c):
        import pprint
        d = self.a.fixdiff(b)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(d)
        self.assertEqual(c, d, "fixdiff Excepted %s to %s but get %s" % (b, c, d))

    def test(self):
        self.check([[None]], [[None]] )
        self.check({"t": "v"}, [[{"~": {"t": "v"}}]] )
        self.check({"~": {"t": "v"}}, [[{"~": {"t": "v"}}]] )
        self.check({"~": {"t": "v"}, "+": {"t": "v"}}, [[{"~": {"t": "v"}, "+": {"t": "v"}}]] )
        self.check([{"~": {"t": "v"}, "+": {"t": "v"}}], [[{"~": {"t": "v"}, "+": {"t": "v"}}]] )
        self.check([{"~": {"t": "v"}}, {"+": {"t": "v"}}], [[{"~": {"t": "v"}}], [{"+": {"t": "v"}}]] )
        self.check([[{"t": "v"}], [{"t": "v"}]], [[{"~": {"t": "v"}}], [{"~": {"t": "v"}}]] )
        self.check([[None, {"t": "v"}]], [[None, {"~": {"t": "v"}}]] )
