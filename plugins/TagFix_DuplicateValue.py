#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Etienne Chové <chove@crans.org> 2009                       ##
## Copyrights Frédéric Rodrigo 2011-2015                                 ##
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

import re
import itertools
from modules.Stablehash import stablehash64
from modules.OsmoseTranslation import T_
from plugins.Plugin import Plugin

class TagFix_DuplicateValue(Plugin):

    def init(self, logger):
        Plugin.init(self, logger)
        doc = dict(
            detail = T_(
'''The tag contains two values (separated by ';') which are very
similar.'''),
            fix = T_(
'''Delete one value.'''),
            trap = T_(
'''In some case all values maybe required.'''))
        self.errors[3060]  = self.def_class(item = 3060, level = 3, tags = ['value', 'fix:chair'],
            title = T_('Duplicated values'),
            **doc)
        self.errors[30601] = self.def_class(item = 3060, level = 3, tags = ['value', 'fix:chair'],
            title = T_('Similar values'),
            resource = 'https://en.wikipedia.org/wiki/Levenshtein_distance',
            **doc)

        self.BlackList = set((
            'ref', 'created_by', 'is_in',
            'CLC:id', 'GNS:id', 'tmc', 'tiger:cfcc', 'statscan:rbuid',
            'source:geometry:date', 'source:geometry:ref', # Belgium, Flanders
            'source:date',
            'service_times', 'collection_times',
            'phone', 'contact:phone', 'fax', 'contact:fax',
            'url',
            'technology', 'cables', 'position', 'passenger', 'couplings:diameters',
            'healthcare:speciality',
            'traffic_sign',
            'sport',
            'addr:flats', 'addr:housenumber', 'addr:unit', 'addr:floor', 'addr:block', 'addr:door',
        ))
        self.BlackListRegex = set((
            re.compile('seamark:.+:colour'),
            re.compile('.+_ref'), re.compile('ref:.+'),
            re.compile('destination:.+'),
            re.compile('AND_.+'), re.compile('AND:.+'),
            re.compile('[Nn][Hh][Dd]:.+'),
            re.compile('massgis:.+'),
            re.compile('maxspeed(:.+)?'),
            re.compile('maxheight(:.+)?'),
            re.compile('maxwidth(:.+)?'),
            re.compile('maxweight(:.+)?'),
            re.compile('lacounty:.+'),
            re.compile('.+:conditional'),
            re.compile('railway:signal:.+'),
            re.compile('turn:lanes.*'),
            re.compile('opening_hours(:.+)?'),
       ))

    # http://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python
    def levenshtein(self, s1, s2):
        if len(s1) < len(s2):  # pragma: no cover
            return self.levenshtein(s2, s1)
        if not s1:  # pragma: no cover
            return len(s2)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1 # j+1 instead of j since previous_row and current_row are one character longer
                deletions = current_row[j] + 1 # than s2
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def node(self, data, tags):
        err = []
        keys = tags.keys()
        for k in keys:
            if k in self.BlackList:
                continue

            try:
                for blr in self.BlackListRegex:
                    if blr.match(k):
                        raise Exception
            except Exception:
                continue

            v = tags[k]
            if k == 'source':
                v = v.replace('Cadastre ; mise', 'Cadastre, mise') # France
                v = v.replace('GSImaps/ort', 'GSImaps/std') # Japan
            if ';' in v:
                vs = list(filter(lambda w: len(w) > 0, map(lambda w: w.strip(), v.split(';'))))
                if len(vs) != len(set(vs)):
                    err.append({"class": 3060, "subclass": stablehash64(k),
                                "text": T_("Duplicated values {key}={val}", key = k, val = tags[k]),
                                "fix": {k: ";".join(set(vs))} })
                else:
                    vs_long = filter(lambda w: len(w) > 6, vs)
                    for v1,v2 in itertools.combinations(vs_long, 2):
                        if abs(len(v1)-len(v2)) < 4 and self.levenshtein(v1, v2) < 4:
                            err.append({"class": 30601, "subclass": stablehash64(k),
                                        "text": T_("Duplicated similar values {key}={val}", key = k, val = tags[k])})
                            break

        return err

    def way(self, data, tags, nds):
        return self.node(data, tags)

    def relation(self, data, tags, members):
        return self.node(data, tags)


###########################################################################
from plugins.Plugin import TestPluginCommon

class Test(TestPluginCommon):
    def test(self):
        a = TagFix_DuplicateValue(None)
        a.init(None)

        for t in [{"oneway":"yes;yes"},
                  {"oneway":"yes;yes;no"},
                  {"oneway":"yes;yes;yes;yes;-1;-1;no;no"},
                  {"source":u"cadastre-dgi-fr source : Direction Générale des Impôts - Cadastre ; mise à jour : 2013;cadastre-dgi-fr source : Direction Générale des Impôts - Cadastre ; mise à jour : 2013"},
                  {"source":u"cadastre-dgi-fr source : Direction Générale des Impôts - Cadastre ; mise à jour : 2010;cadastre-dgi-fr source : Direction Générale des Impôts - Cadastre ; mise à jour : 2013"},
                  {"source":"GSImaps/ort;GSImaps/std"},
                 ]:
            self.check_err(a.node(None, t), t)
            self.check_err(a.way(None, t, None), t)
            self.check_err(a.relation(None, t, None), t)

        for t in [{"ref":"E 05; E 70; E 05;E 70; E 05;E 70; E 05;E 70; E 05;E 70"},
                  {"seamark:buoy_lateral:colour":"red;white;red;white"},
                  {"ref:mhs":"IA00070520; IA00070492"},
                  {"opening_hours": "Mo 14:00-19:00; Tu-Fr 10:00-14:00,15:00-19:00; Sa 10:00-19:00"},
                  {"oneway":"yes;no"},
                  {"AND_toto":"121;121;121"},
                  {"NHD:ComID":"141725410;141725411"},
                  {"massgis:OS_ID":"305-735;305-764"},
                 ]:
            assert not a.node(None, t), t
