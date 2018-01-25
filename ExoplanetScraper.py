import urllib.request, csv
from urllib.parse import quote
from datetime import datetime

OEC_TO_EXO_SYSTEM = {'rightascension':'ra', 'declination':'dec', 'distance':'star_distance'}
OEC_TO_EXO_STAR= {'mass':'star_mass', 'radius':'star_radius','magI':'mag_i', 'magV':'mag_v', 'magI':'mag_i','magJ':'mag_j','magH':'mag_h','magK':'mag_k', 'metallicity':'star_metallicity', 'spectraltype':'star_sp_type', 'temperature':'star_teff', 'age':'star_age'}
OEC_TO_EXO_PLANET = {'mass':'mass', 'radius':'radius', 'period':'orbital_period', 'semimajoraxis':'semi_major_axis', 'eccentricity':'eccentricity', 'periastron':'omega', 'periastrontime':'tperi', 'discoverymethod':'detection_type', 'discoveryyear':'discovered', 'inclination':'inclination', 'transittime':'tzero_tr', 'temperature':'temp_calculated', 'impactparameter' : 'impact_parameter'}
#values from oec and exoplanet.eu that are deemed equal
OEC_TO_EXO_VALUES = {'transit' : 'Primary Transit', 'RV' : 'Radial Velocity'}

def get_exoplanet_data_since(date):
    '''
    Given a date (YYYY-MM-DD), return a list of dict (each dict being a row from exoplanet.eu)
    of all the data from exoplanet.eu that has been updated after that date
    '''
    updated = []
    url = 'http://exoplanet.eu/catalog/csv'
    response = urllib.request.urlopen(url).read()
    reader = csv.reader(response.decode('utf-8').splitlines(), delimiter=',')
    #columns names are the first row in the csv reader
    columns = next(reader)
    
    for row in reader:
        last_update = datetime.strptime(date, '%Y-%m-%d')
        eu_update = datetime.strptime(row[24], '%Y-%m-%d')
        if(eu_update >= last_update):
            planet_dict = {}
            #map each column name to each row value
            for i in range(len(columns)):
                planet_dict[columns[i]] = row[i]
            updated.append(planet_dict)
    return updated


def get_updated_systems_exoplanet(updated_exo_data, oec):
    '''
    Given a list of dicts (each dict being a row of data from exoplanet.eu)
    and an ElementTree representing OEC data, return a dict containing the changes
    between them
    ''' 
    updated_systems = {}
    for row in updated_exo_data:
        #loop through all systems in oec
        for system in oec.findall('.//system'):
            #loop through all stars in current system
            for star in system.findall('.//star'):
                #get all the alternative star names from exo
                alt_names = []
                if row['star_alternate_names'] != '':
                    alt_names = row['star_alternate_names'].split(', ')
                alt_names.append(row['star_name'])
                if same_name(star, alt_names):
                    #get system changes
                    system_changes(system, row, updated_systems)
                    #get changes to stars
                    star_changes(system, star, row, updated_systems)
                    #loop through all the planets in current star
                    found_planet = False
                    for planet in star.findall('.//planet'):
                        #get all the alternative star names from exo
                        alt_names = []
                        if row['alternate_names'] != '':
                            alt_names = row['alternate_names'].split(', ')
                        alt_names.append(row['# name'])
                        if same_name(planet, alt_names):
                            found_planet = True
                            #get planet changes
                            planet_changes(system, star, planet, row, updated_systems)
                    #if planet wasn't found, then its new
                    if not found_planet:
                        #get data for the new planet
                        new_planet(system, star, row, updated_systems)
    return updated_systems

def system_changes(system, row, updated_systems):
    '''
    Update the 'updated_systems' dict with changes found between the
    exoplanet system data and the given system element node
    '''
    system_attributes = {}
    for attribute in OEC_TO_EXO_SYSTEM:
        exo_system_attribute = row[OEC_TO_EXO_SYSTEM[attribute]]
        oec_system_attribute = system.findtext(attribute)

        #do any conversions needed for the required attributes
        if attribute == 'rightascension' and exo_system_attribute != '':
            exo_system_attribute = ra_deg_to_HMS(float(exo_system_attribute))
        if attribute == 'declination' and exo_system_attribute != '':
            exo_system_attribute = dec_deg_to_HMS(float(exo_system_attribute))
        
        #make sure exo value is not empty and both values are different
        if (exo_system_attribute != '') and (not same_values(attribute, oec_system_attribute, exo_system_attribute)):
            #get any error values from exo for the attribute
            error_values = get_exo_error_values(row, OEC_TO_EXO_SYSTEM[attribute])
            exo_values = [error_values[0], exo_system_attribute, error_values[1]]

            error_values = get_oec_error_values(system, attribute)
            oec_values = [error_values[0], oec_system_attribute, error_values[1]]
            system_attributes[attribute] = [oec_values, exo_values]

    if (len(system_attributes) != 0):

        source_url = get_source_link(row['# name'])
        system_attributes['reference'] = [[None, None, None], [None, source_url, None]]

        if system.findtext('name') in updated_systems:
            updated_systems[system.findtext('name')]['attributes'].update(system_attributes)
        else:
            updated_systems[system.findtext('name')] = {'attributes':system_attributes, 'stars':{}}

def star_changes(system, star, row, updated_systems):
    '''
    Update the 'updated_systems' dict with changes found between the exoplanet star data
    and the given star element node
    REQ: Star element node must be in the system element node
    '''
    changed_star_attributes = {}
    #loop through all the attributes untill we find a change
    for attribute in OEC_TO_EXO_STAR:    
        exo_star_attribute = row[OEC_TO_EXO_STAR[attribute]]
        oec_star_attribute = star.findtext(attribute)
    
        #make sure exo value is not empty and both values are different
        if (exo_star_attribute != '') and (not same_values(attribute, oec_star_attribute, exo_star_attribute)):
            #get any error values from exo for the attribute
            error_values = get_exo_error_values(row, OEC_TO_EXO_STAR[attribute])
            exo_values = [error_values[0], exo_star_attribute, error_values[1]]

            error_values = get_oec_error_values(star, attribute)
            oec_values = [error_values[0], oec_star_attribute, error_values[1]]

            changed_star_attributes[attribute] = [oec_values, exo_values]

    #get any new aliases for the star
    new_aliases = ''
    if row['star_alternate_names'] != '':
        alt_names = row['star_alternate_names'].split(', ')
        alt_names.append(row['star_name'])
        new_aliases = get_new_aliases(star, alt_names)
    if new_aliases != '':
        changed_star_attributes['new names'] =  [[None, None, None], [None, new_aliases, None]]

    if (len(changed_star_attributes) != 0):
        changed_star_attributes['new'] = 0

        source_url = get_source_link(row['# name'])
        changed_star_attributes['reference'] = [[None, None, None], [None, source_url, None]]

        if system.findtext('name') in updated_systems:
            if not (star.findtext('name') in updated_systems[system.findtext('name')]['stars']):
                    updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes': changed_star_attributes, 'planets':{}}
        else:
            updated_systems[system.findtext('name')] = {'attributes':{}, 'stars':{}}
            updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes': changed_star_attributes, 'planets':{}}

def planet_changes(system, star, planet, row, updated_systems):
    '''
    Update the 'updated_systems' dict with changes found between the exoplanet planet data
    and the given planet element node
    REQ: Planet node must be in the star node and star node must be in the system element node
    '''
    changed_planet_attributes = {}
    for attribute in OEC_TO_EXO_PLANET:
        oec_planet_attribute = planet.findtext(attribute)
        exo_planet_attribute = row[OEC_TO_EXO_PLANET[attribute]]

        #make sure exo value is not empty and both values are different
        if (exo_planet_attribute != '') and (not same_values(attribute, oec_planet_attribute, exo_planet_attribute)):
            #get error values from oec for that attribute
            error_values = get_oec_error_values(planet, attribute)
            oec_values = [error_values[0], oec_planet_attribute, error_values[1]]
            #get error values from exoplanet for that attribute
            error_values = get_exo_error_values(row, OEC_TO_EXO_PLANET[attribute])
            exo_values = [error_values[0], exo_planet_attribute, error_values[1]]

            changed_planet_attributes[attribute] = [oec_values, exo_values]

    #get any new aliases for the planet
    aliases = ''
    if row['alternate_names'] != '':
        alt_names = row['alternate_names'].split(', ')
        alt_names.append(row['# name'])
        aliases = get_new_aliases(planet, alt_names)
    if aliases != '':
        changed_planet_attributes['new names'] =  [[None, None, None], [None, aliases, None]]

    if (len(changed_planet_attributes) != 0):
        changed_planet_attributes['new'] = 0

        source_url = get_source_link(row['# name'])
        changed_planet_attributes['reference'] = [[None, None, None], [None, source_url, None]]

        if system.findtext('name') in updated_systems:
            if star.findtext('name') in updated_systems[system.findtext('name')]['stars']:
                updated_systems[system.findtext('name')]['stars'][star.findtext('name')]['planets'][planet.findtext('name')] = changed_planet_attributes
            else:
                updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes':{}, 'planets':{planet.findtext('name'):changed_planet_attributes}}
        else:
            updated_systems[system.findtext('name')] = {'attributes':{}, 'stars':{}}
            updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes':{}, 'planets':{planet.findtext('name'):changed_planet_attributes}}

def new_planet(system, star, row, updated_systems):
    '''
    Update the 'updated_systems' dict with new planet data found in the exoplanet planet data
    REQ: star node must be in the system element node
    '''
    new_planet_attributes = {}
    for attribute in OEC_TO_EXO_PLANET:
        new_exo_planet_attribute = row[OEC_TO_EXO_PLANET[attribute]]

        for oec_val in OEC_TO_EXO_VALUES:
            if new_exo_planet_attribute == OEC_TO_EXO_VALUES[oec_val]:
                new_exo_planet_attribute = oec_val

        if (new_exo_planet_attribute != ''):
            oec_values = [None, None, None]
            #get error values from exoplanet for that attribute
            error_values = get_exo_error_values(row, OEC_TO_EXO_PLANET[attribute])
            exo_values = [error_values[0], new_exo_planet_attribute, error_values[1]]

            new_planet_attributes[attribute] = [oec_values, exo_values]

    #get the alternate names for the new planet
    if row['alternate_names'] != '':
        new_planet_attributes['new names'] =  [[None, None, None], [None, row['alternate_names'], None]]

    if (len(new_planet_attributes) != 0):
        new_planet_attributes['new'] = 1

        source_url = get_source_link(row['# name'])
        new_planet_attributes['reference'] = [[None, None, None], [None, source_url, None]]

        if system.findtext('name') in updated_systems:
            if star.findtext('name') in updated_systems[system.findtext('name')]['stars']:
                updated_systems[system.findtext('name')]['stars'][star.findtext('name')]['planets'][row['# name']] = new_planet_attributes
            else:
                updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes':{}, 'planets':{row['# name']:new_planet_attributes}}
        else:
            updated_systems[system.findtext('name')] = {'attributes':{}, 'stars':{}}
            updated_systems[system.findtext('name')]['stars'][star.findtext('name')] = {'attributes':{}, 'planets':{row['# name']:new_planet_attributes}}

def same_values(attribute, oec_value, exo_value):
    '''
    Given the oec attribute and the corresponding value from oec and exoplanet
    return True if they are equivalent
    '''
    #if oec is None or exo is '', means values are empty
    if oec_value == None or exo_value == '':
        return oec_value == exo_value
    try:
        #try comparing as floats
        return float(oec_value) == float(exo_value)
    except:
        #do special comparison for 'rightascension' or 'declinations'
        if (attribute == 'rightascension') or (attribute == 'declination'):
            return compare_coordinates(oec_value, exo_value)
        #otherwise check for special cases
        if oec_value in OEC_TO_EXO_VALUES:
            return exo_value == OEC_TO_EXO_VALUES[oec_value]
        #otherwise to do normal comparison
        return (oec_value == exo_value) or (str(oec_value).replace(' ', '').lower() == str(exo_value).replace(' ', '').lower())

def get_oec_error_values(xml_node, attribute):
    '''
    Given a xml node and an attribute name in oec,
    return a list of 2 error values in the form [errorminus, errorplus]
    '''
    error_values = [None, None]
    xml_element = xml_node.find(attribute)
    if xml_element != None:
        xml_attributes =  xml_element.attrib
        if 'errorminus' in xml_attributes:
            error_values[0] = xml_attributes['errorminus']
        if 'errorplus' in xml_attributes:
            error_values[1] = xml_attributes['errorplus']
    return error_values

def get_exo_error_values(row, attribute):
    '''
    Given a dict representing a row of data and column name from exoplanet.eu
    return a list of 2 error values in the form [errorminus, errorplus] 
    '''
    error_values = [None, None]
    if attribute + '_error_min' in row:
        if row[attribute + '_error_min'] != '':
            error_values[0] = row[attribute + '_error_min']
    if attribute + '_error_max' in row:
        if row[attribute + '_error_max'] != '':
            error_values[1] = row[attribute + '_error_max']
    return error_values

def get_source_link(planet_name):
    '''
    Given a planet name return the exoplanet link containg the planet info and sources
    '''
    source_url = 'http://exoplanet.eu/catalog/'
    planet_name = planet_name.lower().replace(' ', '_')
    source_url += quote(planet_name) + '/'
    return source_url

def get_new_aliases(xml_node, exo_alias):
    '''
    Given an XML Node from oec, and a list of alternate names from exoplanet,
    return a string of names that are exoplanet alternate names, but aren't in the
    name tags of the xml node, separated by commas
    '''
    first_name = True
    new_aliases = ''
    for alias in exo_alias:
        found = False
        for name in xml_node.findall('name'):
            if name.text == alias:
                found = True
                break
        if not found:
            if first_name:
                new_aliases += alias
                first_name = False
            else:
                new_aliases += ', ' + alias
    return new_aliases

def same_name(xml_node, exo_alias):
    '''
    Given an XML Node, and a list of alternate names from exoplanet,
    return true if the xml node has a name tag that matches one of the exo planet names
    '''
    #for each name in the xml_node, compare to exo alternate names
    for alias in exo_alias:
        for name in xml_node.findall('name'):
            #if found return true
            if name.text == alias:
                return True
    #otherwise, alias name not found
    return False
  
def ra_deg_to_HMS(ra):
    '''
    Given the right ascension in degrees, convert to time in the format 'hh mm ss'
    '''
    hour = int(ra/15)
    hour_str = str(hour)
    if (len(hour_str) == 1):
        hour_str = '0'+ hour_str

    minute = int(((ra/15)-hour)*60)
    minute_str = str(minute)
    if (len(minute_str) == 1):
        minute_str = '0'+ minute_str

    second = round((((((ra/15)-hour)*60)-minute)*60), 1)
    second_str = str(second)
    if (len(second_str.split('.')[0]) == 1):
        second_str = '0'+ second_str

    return (hour_str + ' ' + minute_str + ' ' + second_str)

def dec_deg_to_HMS(dec):
    '''
    Given the declination in degrees, convert to the time in the format 'dd mm ss'
    '''
    sign = '+'
    if str(dec)[0] == '-':
        sign, dec = '-', abs(dec)

    deg = int(dec)
    deg_str = str(deg)
    if (len(deg_str) == 1):
        deg_str = '0' + deg_str

    arc_min = abs(int((dec-deg)*60))
    arc_min_str = str(arc_min)
    if (len(arc_min_str) == 1):
        arc_min_str = '0' + arc_min_str

    arc_sec = round((abs((dec-deg)*60)-arc_min)*60)
    arc_sec_str = str(arc_sec)
    if (len(arc_sec_str) == 1):
        arc_sec_str = '0' + arc_sec_str

    return (sign + deg_str + ' ' + arc_min_str + ' ' + arc_sec_str)

def compare_coordinates(oec_coordinates, exo_coordinates):
    '''
    Given coordinates from oec and exo, compare the two
    and return true if equivalent
    REQ: format of coordinates must be in the form 'hh mm ss' or 'dd mm ss'
    '''
    oec_values = oec_coordinates.split(" ")
    exo_values = exo_coordinates.split(" ")

    for i in range(len(oec_values)):
        if float(oec_values[i]) != float(exo_values[i]):
            return False
    return True

def date_exo_to_oec(date):
    '''
    Given date in format YYYY-MM-DD, return the date in the format YY/MM/DD
    '''
    return datetime.strptime(date, '%Y-%m-%d').strftime('%y/%m/%d')

def changes_since(date, oec):
    '''
    Given the date(YYYY-MM-DD) and an ElementTree representing the OEC data,
    return a dict containing the changes between the Exoplanet and OEC catalogs
    '''
    exo = get_exoplanet_data_since(date)
    return get_updated_systems_exoplanet(exo, oec)
