-- Read views for the API: geometry as GeoJSON so PostgREST / supabase-py return usable JSON.
-- security_invoker = true keeps the base tables' RLS policies in force.

create or replace view v_districts with (security_invoker = true) as
select id, lgd_code, state_id, name, name_te, name_hi, ST_AsGeoJSON(geom, 6)::json as geom
from districts;

create or replace view v_blocks with (security_invoker = true) as
select id, lgd_code, district_id, name, name_te, name_hi, mean_elevation_m, ST_AsGeoJSON(geom, 6)::json as geom
from blocks;

create or replace view v_panchayats with (security_invoker = true) as
select id, lgd_code, block_id, name, name_te, name_hi, elevation_m, registered_farmers,
       ST_AsGeoJSON(geom, 6)::json as geom,
       ST_AsGeoJSON(centroid, 6)::json as centroid
from panchayats;

create or replace view v_aws_stations with (security_invoker = true) as
select id, code, name, lat, lon, elevation_m, panchayat_id, used_in_training
from aws_stations;
