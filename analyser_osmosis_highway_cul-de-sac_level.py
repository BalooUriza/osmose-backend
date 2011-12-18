#!/usr/bin/env python
#-*- coding: utf-8 -*-

###########################################################################
##                                                                       ##
## Copyrights Frédéric Rodrigo 2011                                      ##
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

import sys, re, popen2, urllib, time
import psycopg2
from modules import OsmSax
from modules import OsmOsis

###########################################################################

sql10 = """
CREATE OR REPLACE FUNCTION ends(nodes bigint[]) RETURNS SETOF bigint AS $$
DECLARE BEGIN
    RETURN NEXT nodes[1];
    RETURN NEXT nodes[array_length(nodes,1)];
    RETURN;
END
$$ LANGUAGE plpgsql;


DROP VIEW IF EXISTS highway_level CASCADE;
CREATE VIEW highway_level AS
SELECT
    id,
    nodes,
    tags?'junction' AS junction,
    CASE tags->'highway'
        WHEN 'motorway' THEN 1
        WHEN 'primary' THEN 1
        WHEN 'trunk' THEN 1
        WHEN 'motorway_link' THEN 2
        WHEN 'primary_link' THEN 2
        WHEN 'trunk_link' THEN 2
        WHEN 'secondary' THEN 2
        WHEN 'secondary_link' THEN 2
        WHEN 'tertiary' THEN 3
        WHEN 'tertiary_link' THEN 3
        WHEN 'unclassified' THEN 4
        WHEN 'unclassified_link' THEN 4
        WHEN 'residential' THEN 4
        WHEN 'residential_link' THEN 4
        ELSE 5
    END AS level
FROM
    ways
WHERE
    tags?'highway'
;

DROP VIEW IF EXISTS way_ends CASCADE;
CREATE VIEW way_ends AS
SELECT
    id,
    ends(nodes) AS nid,
    level
FROM
    highway_level
WHERE
    NOT junction
;


SELECT
    way_ends.id,
    ST_X(nodes.geom),
    ST_Y(nodes.geom),
    way_ends.level
FROM
    way_ends
    JOIN way_nodes ON
        way_ends.nid = way_nodes.node_id AND
        way_nodes.way_id != way_ends.id
    JOIN highway_level ON
        way_nodes.way_id = highway_level.id
    JOIN nodes ON
        nodes.id = way_ends.nid
GROUP BY
    way_ends.id,
    way_ends.nid,
    way_ends.level,
    nodes.geom
HAVING
    way_ends.level + 1 < MIN(highway_level.level)
;
"""

###########################################################################

def analyser(config, logger = None):

    gisconn = psycopg2.connect(config.dbs)
    giscurs = gisconn.cursor()
    apiconn = OsmOsis.OsmOsis(config.dbs, config.dbp)

    ## output headers
    outxml = OsmSax.OsmSaxWriter(open(config.dst, "w"), "UTF-8")
    outxml.startDocument()
    outxml.startElement("analyser", {"timestamp":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    outxml.startElement("class", {"id":"1", "item":"1090"})
    outxml.Element("classtext", {"lang":"fr", "title":"Mauvaise topologie de niveau de voies"})
    outxml.Element("classtext", {"lang":"en", "title":"Bad topology way level"})
    outxml.endElement("class")
    outxml.startElement("class", {"id":"2", "item":"1090"})
    outxml.Element("classtext", {"lang":"fr", "title":"Mauvaise topologie de niveau de voies"})
    outxml.Element("classtext", {"lang":"en", "title":"Bad topology way level"})
    outxml.endElement("class")
    outxml.startElement("class", {"id":"3", "item":"1090"})
    outxml.Element("classtext", {"lang":"fr", "title":"Mauvaise topologie de niveau de voies"})
    outxml.Element("classtext", {"lang":"en", "title":"Bad topology way level"})
    outxml.endElement("class")

    ## querries
    logger.log(u"requête osmosis")
    giscurs.execute("SET search_path TO %s,public;" % config.dbp)
    giscurs.execute(sql10)

    ## output data
    logger.log(u"génération du xml")
    for res in giscurs.fetchall():
        outxml.startElement("error", {"class":str(res[3])})
        outxml.Element("location", {"lat":str(res[2]), "lon":str(res[1])})
        outxml.WayCreate(apiconn.WayGet(res[0]))
        outxml.endElement("error")

    ## output footers
    outxml.endElement("analyser")
    outxml._out.close()

    ## close database connections
    giscurs.close()
    gisconn.close()
    del apiconn
