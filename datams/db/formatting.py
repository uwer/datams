import os
import datetime as dt
import pandas as pd
from flask import url_for

from datams.utils import MAP_CONFIG, TIMEZONES_R
from datams.utils import get_colors, svg_d_value, jpgbytes_to_base64

MOORING_ICON = MAP_CONFIG['MOORING_ICON']


# TODO: Rename compute add_columns

def setup_compute(df, compute):
    compute = set() if compute is None else set(compute)
    if df.empty and compute:
        df[list(compute)] = None
    return df, compute


def remaing_compute_check(compute):
    if len(compute) > 0:
        raise NotImplementedError(f"No logic exists to compute the following "
                                  f"column(s): `{compute}`")


# TODO: Consider putting this into the utils as it is useful in calc as well
def meets_requirements(compute, current, requires, received):
    if current in compute:
        compute.remove(current)
        if not set(requires).issubset(received):
            raise RuntimeError(f"column(s): `{requires}` are required to compute "
                               f"column: `{current}`.  However only received "
                               f"column(s): {received}")
        return True

    return False


# TODO: Consider adding default avatar info here if it that column value is None
def contact_format(df, compute):
    df, compute = setup_compute(df, compute)
    if df.empty:
        return df

    if 'avatar' in df.columns:
        df['avatar'] = df['avatar'].apply(
            lambda x: x if pd.isna(x) else jpgbytes_to_base64(x)
        )

    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: url_for('contact.details', cid=x))

    if meets_requirements(compute, 'name', ['first_name', 'last_name'], df.columns):
        df['name'] = df.fillna('').apply(
            lambda x: ', '.join(
                [i for i in [x['last_name'], x['first_name']] if i != '']
            ),
            axis=1
        )

    remaing_compute_check(compute)

    return df


def deployment_format(df, compute=None):
    df, compute = setup_compute(df, compute)
    if df.empty:
        return df

    if 'oids' in df.columns:
        df['oids'] = df['oids'].apply(lambda x: [int(i) for i in x.split(',')])

    if 'date' in df.columns:
        df['date'] = df['date'].apply(lambda x: x if pd.isna(x) else
                                                dt.datetime.fromtimestamp(x).date())
    if 'organizations' in df.columns:
        df['organizations'] = df['organizations'].apply(
            lambda x: x if pd.isna(x) else ', '.join(x.split(',')))

    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: url_for('deployment.details', did=x))

    if meets_requirements(compute, 'name',
                          ['region', 'country', 'date', 'organizations'], df.columns):
        df['name'] = df.apply(lambda x: f"[{x['organizations']}] -- {x['region']}, "
                                        f"{x['country']} -- {x['date']}", axis=1)

    if meets_requirements(compute, 'location', ['region', 'country'], df.columns):
        df['location'] = df.apply(lambda x: ', '.join([x['region'], x['country']])
                                            if x['region'] != x['country']
                                            else x['region'], axis=1)
    remaing_compute_check(compute)

    return df


def file_format(df, compute, level=None):
    df, compute = setup_compute(df, compute)
    if df.empty:
        return df

    assert level in [None, 'organization', 'deployment', 'mooring_equipment', 'unowned']

    if (level == 'organization' and
            meets_requirements(compute, 'deployment_id', [], df.columns)):
        df['deployment_id'] = None

    if (level in ['organization', 'deployment'] and
            meets_requirements(compute, 'mooring_id', [], df.columns)):
        df['mooring_id'] = None

    if (level in ['organization', 'deployment'] and
            meets_requirements(compute, 'equipment_id', [], df.columns)):
        df['equipment_id'] = None

    if 'uploaded' in df.columns:
        df['uploaded'] = df['uploaded'].apply(
            lambda x: x if pd.isna(x) else
            dt.datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S')
        )
    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: f"/file/details/{x}")
        # df['url'] = df['id'].apply(lambda x: url_for('dfile.details', fid=x))

    if meets_requirements(compute, 'filename', ['path', 'name'], df.columns):
        df['filename'] = df.apply(
            lambda x: os.path.basename(x['path']) if pd.isna(x['name']) else x['name'],
            axis=1
        )

    if 'level' in compute:
        if level is not None:
            compute.remove('level')
            df['level'] = level.replace('_', ' ').title()
        elif meets_requirements(compute, 'level', ['organization_id', 'deployment_id',
                                                   'mooring_equipment_id'], df.columns):
            def get_level(r):
                for i in ['mooring_equipment', 'deployment', 'organization']:
                    if r[f"{i}_id"] is not None:
                        return i.replace('_', ' ').title()
            df['level'] = df.apply(get_level, axis=1)

    if 'owner' in compute:
        if level is None:
            raise RuntimeError("Can't determine owner without providing level.  ")
        elif level == 'unowned' and meets_requirements(compute, 'owner', [],
                                                       df.columns):
            df['owner'] = ''
        elif level == 'organization' and meets_requirements(compute, 'owner', ['org'],
                                                            df.columns):
            df['owner'] = df['org']
        elif (level == 'deployment' and
              meets_requirements(compute, 'owner', ['dep_org', 'dep_dat', 'dep_cou',
                                                    'dep_reg'], df.columns)):
            def generate_dep_owner(r: pd.Series):
                o = ', '.join(r['dep_org'].split(','))
                d = ('' if pd.isna(r['dep_dat'])
                     else dt.datetime.fromtimestamp(r['dep_dat']).date())
                return f"[{o}] {r['dep_reg']}, {r['dep_cou']} -- {d}"
            df['owner'] = df.apply(generate_dep_owner, axis=1)
        elif (level == 'mooring_equipment' and
              meets_requirements(compute, 'owner',
                                 ['me_org', 'me_reg', 'me_cou', 'me_dep', 'me_rec',
                                  'me_lat', 'me_lon'], df.columns)):
            def generate_me_owner(r: pd.Series):
                o = ', '.join(r['me_org'].split(','))
                s = ('' if pd.isna(r['me_dep'])
                     else dt.datetime.fromtimestamp(r['me_dep']).strftime(
                    '%b%d-%Y@%H:%M:%S'))
                e = ('' if pd.isna(r['me_rec'])
                     else dt.datetime.fromtimestamp(r['me_rec']).strftime(
                    '%b%d-%Y@%H:%M:%S'))
                return f"[{o}] {r['me_reg']}, {r['me_cou']} -- [{s} to {e}] -- " \
                       f"[Lat: {r['me_lat']} Lon: {r['me_lon']}]"
            df['owner'] = df.apply(generate_me_owner, axis=1)

    remaing_compute_check(compute)

    return df


def equipment_format(df, compute=None):
    compute = set() if compute is None else set(compute)
    if df.empty and compute:
        df[list(compute)] = None
        return df

    if 'mids' in df.columns:
        df['mids'] = df['mids'].apply(lambda x: [] if x is None
                                      else [int(i) for i in x.split(',')])

    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: url_for('equipment.details', eid=x))

    if meets_requirements(compute, 'make_&_model', ['make', 'model'], df.columns):
        df['make_&_model'] = df.apply(
            lambda x: ' '.join([i for i in [x['make'], x['model']] if not pd.isna(i)]),
            axis=1
        )

    if meets_requirements(compute, 'name', ['item', 'serial_number'], df.columns):
        df['name'] = df.apply(lambda x: f"{x['item']} [{x['serial_number']}]", axis=1)

    if meets_requirements(compute, 'html', ['item', 'make', 'model', 'serial_number',
                                            'comments'], df.columns):
        def generate_html(r: pd.Series) -> str:
            r = r.copy()  # TODO: Find out if this is necessary
            if not pd.isna(r['serial_number']):
                r['serial_number'] = f"(SN: {r['serial_number']})"
            if not pd.isna(r['item']):
                r['item'] = f"{r['item']} |"
            immsn = ' '.join(
                [r[i] for i in ['item', 'make', 'model', 'serial_number']
                 if not pd.isna(r[i])]
            )
            comments = '' if pd.isna(r['comments']) else f" -- {r['comments']}"
            return f"<li><a href='{r['url']}'>{immsn}{comments}</a></li>"

        df['html'] = df.apply(generate_html, axis=1)

    remaing_compute_check(compute)

    return df


def mooring_format(df, compute=None):
    df, compute = setup_compute(df, compute)
    if df.empty:
        return df

    if 'deployed' in df.columns:
        df['deployed'] = df['deployed'].apply(lambda x: x if pd.isna(x) else
                                                        dt.datetime.fromtimestamp(x))
    if 'recovered' in df.columns:
        df['recovered'] = df['recovered'].apply(lambda x: x if pd.isna(x) else
                                                          dt.datetime.fromtimestamp(x))
    if 'timezone' in df.columns:
        df['timezone'] = df['timezone'].apply(lambda x: TIMEZONES_R[str(x)])

    if meets_requirements(compute, 'latitude', ['latitude'], df.columns):
        df['latitude'] = df['latitude'].apply(lambda x: x if pd.isna(x)
                                              else f"{x}\u00b0")
    if meets_requirements(compute, 'longitude', ['longitude'], df.columns):
        df['longitude'] = df['longitude'].apply(lambda x: x if pd.isna(x)
                                                else f"{x}\u00b0")
    if meets_requirements(compute, 'seafloor_depth', ['seafloor_depth'],
                          df.columns):
        df['seafloor_depth'] = df['seafloor_depth'].apply(lambda x: x if pd.isna(x)
                                                          else f"{x} m")
    if meets_requirements(compute, 'line_length', ['line_length'], df.columns):
        df['line_length'] = df['line_length'].apply(lambda x: x if pd.isna(x)
                                                    else f"{x} m")

    if meets_requirements(compute, 'deployment', ['dep_reg', 'dep_cou', 'dep_orgs'],
                          df.columns):
        df['deployment'] = df.apply(lambda x: f"[{x['dep_orgs']}] -- {x['dep_reg']}, "
                                              f"{x['dep_cou']}", axis=1)

    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: url_for('mooring.details', mid=x))

    if meets_requirements(compute, 'edit_url', ['id'], df.columns):
        df['edit_url'] = df['id'].apply(lambda x: url_for('mooring.edit', mid=x))

    if meets_requirements(compute, 'name', ['eq_items', 'eq_sns', 'latitude',
                                            'longitude'], df.columns):
        def generate_name(row):
            if row['eq_sns'] is not None:
                sns, items = row['eq_sns'].split(','), row['eq_items'].split(',')
                assert len(sns) == len(items)
                retval = ', '.join(sorted(list(set(
                    [sns[i] for i in range(len(sns)) if 'hydrophone' in items[i].lower()]
                ))))
            if row['eq_sns'] is None or retval == '':
                retval = f"(Lat: {row['latitude']}, Lon:{row['longitude']})"
            return retval
        df['name'] = df.apply(generate_name, axis=1)

    if meets_requirements(compute, 'icon', [], df.columns):
        df['icon'] = svg_d_value(os.path.realpath(MOORING_ICON))

    if meets_requirements(compute, 'color', [], df.columns):
        df['color'] = get_colors(df.shape[0])

    if meets_requirements(compute, 'html',
                          ['latitude', 'longitude', 'seafloor_depth', 'line_length',
                           'deployed', 'recovered', 'name', 'id'], df.columns):

        def generate_html(r: pd.Series) -> str:
            r = r.copy().fillna('')
            for i in ['latitude', 'longitude', 'seafloor_depth', 'line_length']:
                if i in ['latitude', 'longitude']:
                    r[i] = f"{r[i]}&deg;" if r[i] != '' else ''
                if i in ['seafloor_depth', 'line_length']:
                    r[i] = f"{r[i]}m" if r[i] != '' else ''

            html = f"<a href='{url_for('mooring.details', mid=r['id'])}'>" \
                   f"<h1>{r['name']}</h1></a><hr><table><tbody><tr>"
            r = r[['deployed', 'recovered', 'latitude', 'longitude', 'seafloor_depth',
                   'line_length']]
            return (html + '</tr><tr>'.join(
                [f"<th>{i.replace('_', ' ').title()}:</th><td>"
                 f"<span class='mapMooringValue'>{r[i]}</span></td>"
                 for i in r.index]) + '</tr></tbody></table>')

        df['html'] = df.apply(generate_html, axis=1)

    remaing_compute_check(compute)

    return df


def organization_format(df, compute=None):
    df, compute = setup_compute(df, compute)
    if df.empty:
        return df

    if meets_requirements(compute, 'url', ['id'], df.columns):
        df['url'] = df['id'].apply(lambda x: url_for('organization.details', oid=x))

    remaing_compute_check(compute)
    return df

