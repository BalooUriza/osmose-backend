#!/usr/bin/env python
#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Frédéric Rodrigo 2018                                      ##
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

from modules.OsmoseTranslation import T_
from .Analyser_Osmosis import Analyser_Osmosis


sql10 = """
CREATE TEMP TABLE starts AS
SELECT
  linestring,
  id
FROM
  ways
WHERE
  tags != ''::hstore AND
  (
    -- Cycle only
    (tags?'railway' AND tags->'railway' = 'platform') OR
    (tags?'public_transport' AND tags->'public_transport' = 'platform') OR
    (tags?'highway' AND tags->'highway' = 'pedestrian') OR
    -- Commons
    (tags?'route' AND tags->'route' = 'ferry') OR
    (tags?'man_made' AND tags->'man_made' = 'pier') OR
    (tags?'aeroway' AND tags->'aeroway' IN ('taxiway', 'runway', 'apron')) OR
    (tags?'railway' AND tags->'railway' = 'platform') OR
    (tags?'highway' AND tags->'highway' IN ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link'))
  )
"""

sql11 = """
CREATE INDEX idx_starts_linestring on starts USING gist(linestring)
"""

sqlb13 = """
CREATE TEMP TABLE islands0 AS
SELECT
  unnest(ST_ClusterIntersecting(linestring)) AS geom
FROM
  highways
WHERE
  NOT highways.is_construction AND
  (NOT tags?'golf' OR tags->'golf' != 'cartpath')
"""

sqlb14 = """
CREATE TEMP TABLE islands AS
SELECT
  ROW_NUMBER () OVER () AS cluster_id,
  ST_SetSRID((ST_Dump(geom)).geom, 4326) AS linestring
FROM
  islands0
"""

sqlb15 = """
DROP TABLE islands0
"""

sqlb16 = """
CREATE INDEX idx_islands_linestring on islands USING gist(linestring)
"""

sqlb17 = """
CREATE TEMP TABLE connected_islands AS
SELECT
  DISTINCT(islands.cluster_id) AS cluster_id
FROM
  islands
  JOIN starts ON
    ST_Intersects(starts.linestring, islands.linestring)
"""

sqlb18 = """
SELECT
  highways.id,
  ST_AsText(way_locate(highways.linestring))
FROM
  highways
  LEFT JOIN islands ON
    islands.cluster_id IN (SELECT cluster_id FROM connected_islands) AND
    ST_Intersects(islands.linestring, highways.linestring)
WHERE
  NOT highways.is_construction AND
  highways.level IS NOT NULL AND
  islands.linestring IS NULL
"""

class Analyser_Osmosis_Highway_Floating_Islands(Analyser_Osmosis):

    requires_tables_common = ['highways']

    def __init__(self, config, logger = None):
        Analyser_Osmosis.__init__(self, config, logger)
        self.classs[4] = self.def_class(item = 1210, level = 1, tags = ['highway'],
            title = T_('Small highway group apart from the main network or with insufficient access upstream'),
            detail = T_(
'''The end of the way is not connected to another way.'''),
            fix = T_(
'''The way or the group of the ways must be connected to an entry point:
* road: `route=ferry`, `man_made=pier`, `aeroway=taxiway|runway|apron`, `railway=platform` or `highway=motorway|motorway_link|trunk|trunk_link|primary|primary_link`,
* bicycle: `railway=platform`, `public_transport=platform` or `highway=pedestrian`.'''))
        self.callback10 = lambda res: {"class":4, "subclass":1, "data":[self.way_full, self.positionAsText]}

    def analyser_osmosis_common(self):
        self.run(sql10)
        self.run(sql11)
        self.run(sqlb13)
        self.run(sqlb14)
        self.run(sqlb15)
        self.run(sqlb16)
        self.run(sqlb17)
        self.run(sqlb18, self.callback10)
