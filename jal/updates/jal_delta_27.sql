BEGIN TRANSACTION;
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 0;
--------------------------------------------------------------------------------
-- Update 'countries' table
--------------------------------------------------------------------------------
CREATE TABLE sqlitestudio_temp_table AS SELECT * FROM countries;

DROP TABLE countries;

CREATE TABLE countries (
    id         INTEGER      PRIMARY KEY
                            UNIQUE
                            NOT NULL,
    name       VARCHAR (64) UNIQUE
                            NOT NULL,
    code       CHAR (3)     UNIQUE
                            NOT NULL,
    iso_code   CHAR (4)     UNIQUE
                            NOT NULL,
    tax_treaty INTEGER      NOT NULL
                            DEFAULT (0)
);

INSERT INTO countries (
                          id,
                          name,
                          code,
                          iso_code,
                          tax_treaty
                      )
                      SELECT id,
                             name,
                             code,
                             code,   -- Need to put code as value should be unique
                             tax_treaty
                        FROM sqlitestudio_temp_table;

DROP TABLE sqlitestudio_temp_table;
--------------------------------------------------------------------------------
-- Update existing records
WITH c_codes(cc, iso_code) AS (VALUES ('xx', '000'), ('ru', '643'), ('us', '840'), ('ie', '372'), ('ch', '756'), ('fr', '250'), ('ca', '124'), ('se', '752'),
                                      ('it', '380'), ('es', '724'), ('au', '036'), ('at', '040'), ('be', '056'), ('gb', '826'), ('de', '276'),
                                      ('cn', '156'), ('fi', '246'), ('nl', '528'), ('gr', '300'), ('bm', '060'), ('br', '076'), ('je', '832'))
UPDATE countries SET iso_code = (SELECT iso_code FROM c_codes WHERE code = c_codes.cc)
WHERE code IN (SELECT cc FROM c_codes);
--------------------------------------------------------------------------------
-- Add the rest of countries
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (22, 'Afghanistan', 'af', '004', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (23, 'Aland Islands', 'ax', '248', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (24, 'Albania', 'al', '008', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (25, 'Algeria', 'dz', '012', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (26, 'American Samoa', 'as', '016', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (27, 'Andorra', 'ad', '020', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (28, 'Angola', 'ao', '024', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (29, 'Anguilla', 'ai', '660', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (30, 'Antarctica', 'aq', '010', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (31, 'Antigua and Barbuda', 'ag', '028', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (32, 'Argentina', 'ar', '032', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (33, 'Armenia', 'am', '051', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (34, 'Aruba', 'aw', '533', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (35, 'Azerbaijan', 'az', '031', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (36, 'Bahamas', 'bs', '044', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (37, 'Bahrain', 'bh', '048', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (38, 'Bangladesh', 'bd', '050', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (39, 'Barbados', 'bb', '052', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (40, 'Belarus', 'by', '112', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (41, 'Belize', 'bz', '084', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (42, 'Benin', 'bj', '204', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (43, 'Bhutan', 'bt', '064', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (44, 'Bolivia', 'bo', '068', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (45, 'Bosnia and Herzegovina', 'ba', '070', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (46, 'Botswana', 'bw', '072', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (47, 'Bouvet Island', 'bv', '074', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (48, 'British Virgin Islands', 'vg', '092', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (49, 'British Indian Ocean Territory', 'io', '086', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (50, 'Brunei Darussalam', 'bn', '096', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (51, 'Bulgaria', 'bg', '100', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (52, 'Burkina Faso', 'bf', '854', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (53, 'Burundi', 'bi', '108', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (54, 'Cambodia', 'kh', '116', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (55, 'Cameroon', 'cm', '120', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (56, 'Cape Verde', 'cv', '132', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (57, 'Cayman Islands', 'ky', '136', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (58, 'Central African Republic', 'cf', '140', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (59, 'Chad', 'td', '148', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (60, 'Chile', 'cl', '152', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (61, 'Hong Kong, SAR China', 'hk', '344', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (62, 'Macao, SAR China', 'mo', '446', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (63, 'Christmas Island', 'cx', '162', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (64, 'Cocos (Keeling) Islands', 'cc', '166', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (65, 'Colombia', 'co', '170', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (66, 'Comoros', 'km', '174', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (67, 'Congo (Brazzaville)', 'cg', '178', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (68, 'Congo, (Kinshasa)', 'cd', '180', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (69, 'Cook Islands', 'ck', '184', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (70, 'Costa Rica', 'cr', '188', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (71, 'Côte d''Ivoire', 'ci', '384', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (72, 'Croatia', 'hr', '191', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (73, 'Cuba', 'cu', '192', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (74, 'Cyprus', 'cy', '196', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (75, 'Czech Republic', 'cz', '203', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (76, 'Denmark', 'dk', '208', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (77, 'Djibouti', 'dj', '262', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (78, 'Dominica', 'dm', '212', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (79, 'Dominican Republic', 'do', '214', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (80, 'Ecuador', 'ec', '218', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (81, 'Egypt', 'eg', '818', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (82, 'El Salvador', 'sv', '222', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (83, 'Equatorial Guinea', 'gq', '226', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (84, 'Eritrea', 'er', '232', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (85, 'Estonia', 'ee', '233', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (86, 'Ethiopia', 'et', '231', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (87, 'Falkland Islands (Malvinas)', 'fk', '238', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (88, 'Faroe Islands', 'fo', '234', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (89, 'Fiji', 'fj', '242', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (90, 'French Guiana', 'gf', '254', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (91, 'French Polynesia', 'pf', '258', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (92, 'French Southern Territories', 'tf', '260', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (93, 'Gabon', 'ga', '266', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (94, 'Gambia', 'gm', '270', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (95, 'Georgia', 'ge', '268', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (96, 'Ghana', 'gh', '288', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (97, 'Gibraltar', 'gi', '292', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (98, 'Greenland', 'gl', '304', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (99, 'Grenada', 'gd', '308', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (100, 'Guadeloupe', 'gp', '312', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (101, 'Guam', 'gu', '316', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (102, 'Guatemala', 'gt', '320', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (103, 'Guernsey', 'gg', '831', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (104, 'Guinea', 'gn', '324', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (105, 'Guinea-Bissau', 'gw', '624', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (106, 'Guyana', 'gy', '328', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (107, 'Haiti', 'ht', '332', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (108, 'Heard and Mcdonald Islands', 'hm', '334', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (109, 'Holy See (Vatican City State)', 'va', '336', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (110, 'Honduras', 'hn', '340', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (111, 'Hungary', 'hu', '348', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (112, 'Iceland', 'is', '352', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (113, 'India', 'in', '356', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (114, 'Indonesia', 'id', '360', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (115, 'Iran, Islamic Republic of', 'ir', '364', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (116, 'Iraq', 'iq', '368', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (117, 'Isle of Man', 'im', '833', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (118, 'Israel', 'il', '376', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (119, 'Jamaica', 'jm', '388', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (120, 'Japan', 'jp', '392', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (121, 'Jordan', 'jo', '400', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (122, 'Kazakhstan', 'kz', '398', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (123, 'Kenya', 'ke', '404', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (124, 'Kiribati', 'ki', '296', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (125, 'Korea (North)', 'kp', '408', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (126, 'Korea (South)', 'kr', '410', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (127, 'Kuwait', 'kw', '414', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (128, 'Kyrgyzstan', 'kg', '417', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (129, 'Lao PDR', 'la', '418', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (130, 'Latvia', 'lv', '428', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (131, 'Lebanon', 'lb', '422', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (132, 'Lesotho', 'ls', '426', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (133, 'Liberia', 'lr', '430', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (134, 'Libya', 'ly', '434', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (135, 'Liechtenstein', 'li', '438', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (136, 'Lithuania', 'lt', '440', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (137, 'Luxembourg', 'lu', '442', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (138, 'Macedonia, Republic of', 'mk', '807', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (139, 'Madagascar', 'mg', '450', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (140, 'Malawi', 'mw', '454', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (141, 'Malaysia', 'my', '458', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (142, 'Maldives', 'mv', '462', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (143, 'Mali', 'ml', '466', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (144, 'Malta', 'mt', '470', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (145, 'Marshall Islands', 'mh', '584', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (146, 'Martinique', 'mq', '474', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (147, 'Mauritania', 'mr', '478', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (148, 'Mauritius', 'mu', '480', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (149, 'Mayotte', 'yt', '175', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (150, 'Mexico', 'mx', '484', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (151, 'Micronesia, Federated States of', 'fm', '583', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (152, 'Moldova', 'md', '498', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (153, 'Monaco', 'mc', '492', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (154, 'Mongolia', 'mn', '496', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (155, 'Montenegro', 'me', '499', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (156, 'Montserrat', 'ms', '500', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (157, 'Morocco', 'ma', '504', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (158, 'Mozambique', 'mz', '508', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (159, 'Myanmar', 'mm', '104', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (160, 'Namibia', 'na', '516', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (161, 'Nauru', 'nr', '520', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (162, 'Nepal', 'np', '524', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (163, 'Netherlands Antilles', 'an', '530', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (164, 'New Caledonia', 'nc', '540', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (165, 'New Zealand', 'nz', '554', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (166, 'Nicaragua', 'ni', '558', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (167, 'Niger', 'ne', '562', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (168, 'Nigeria', 'ng', '566', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (169, 'Niue', 'nu', '570', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (170, 'Norfolk Island', 'nf', '574', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (171, 'Northern Mariana Islands', 'mp', '580', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (172, 'Norway', 'no', '578', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (173, 'Oman', 'om', '512', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (174, 'Pakistan', 'pk', '586', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (175, 'Palau', 'pw', '585', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (176, 'Palestinian Territory', 'ps', '275', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (177, 'Panama', 'pa', '591', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (178, 'Papua New Guinea', 'pg', '598', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (179, 'Paraguay', 'py', '600', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (180, 'Peru', 'pe', '604', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (181, 'Philippines', 'ph', '608', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (182, 'Pitcairn', 'pn', '612', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (183, 'Poland', 'pl', '616', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (184, 'Portugal', 'pt', '620', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (185, 'Puerto Rico', 'pr', '630', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (186, 'Qatar', 'qa', '634', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (187, 'Réunion', 're', '638', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (188, 'Romania', 'ro', '642', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (189, 'Rwanda', 'rw', '646', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (190, 'Saint-Barthélemy', 'bl', '652', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (191, 'Saint Helena', 'sh', '654', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (192, 'Saint Kitts and Nevis', 'kn', '659', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (193, 'Saint Lucia', 'lc', '662', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (194, 'Saint-Martin (French part)', 'mf', '663', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (195, 'Saint Pierre and Miquelon', 'pm', '666', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (196, 'Saint Vincent and Grenadines', 'vc', '670', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (197, 'Samoa', 'ws', '882', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (198, 'San Marino', 'sm', '674', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (199, 'Sao Tome and Principe', 'st', '678', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (200, 'Saudi Arabia', 'sa', '682', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (201, 'Senegal', 'sn', '686', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (202, 'Serbia', 'rs', '688', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (203, 'Seychelles', 'sc', '690', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (204, 'Sierra Leone', 'sl', '694', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (205, 'Singapore', 'sg', '702', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (206, 'Slovakia', 'sk', '703', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (207, 'Slovenia', 'si', '705', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (208, 'Solomon Islands', 'sb', '090', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (209, 'Somalia', 'so', '706', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (210, 'South Africa', 'za', '710', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (211, 'South Georgia and the South Sandwich Islands', 'gs', '239', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (212, 'South Sudan', 'ss', '728', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (213, 'Sri Lanka', 'lk', '144', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (214, 'Sudan', 'sd', '736', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (215, 'Suriname', 'sr', '740', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (216, 'Svalbard and Jan Mayen Islands', 'sj', '744', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (217, 'Swaziland', 'sz', '748', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (218, 'Syrian Arab Republic (Syria)', 'sy', '760', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (219, 'Taiwan, Republic of China', 'tw', '158', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (220, 'Tajikistan', 'tj', '762', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (221, 'Tanzania, United Republic of', 'tz', '834', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (222, 'Thailand', 'th', '764', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (223, 'Timor-Leste', 'tl', '626', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (224, 'Togo', 'tg', '768', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (225, 'Tokelau', 'tk', '772', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (226, 'Tonga', 'to', '776', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (227, 'Trinidad and Tobago', 'tt', '780', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (228, 'Tunisia', 'tn', '788', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (229, 'Turkey', 'tr', '792', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (230, 'Turkmenistan', 'tm', '795', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (231, 'Turks and Caicos Islands', 'tc', '796', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (232, 'Tuvalu', 'tv', '798', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (233, 'Uganda', 'ug', '800', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (234, 'Ukraine', 'ua', '804', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (235, 'United Arab Emirates', 'ae', '784', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (236, 'US Minor Outlying Islands', 'um', '581', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (237, 'Uruguay', 'uy', '858', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (238, 'Uzbekistan', 'uz', '860', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (239, 'Vanuatu', 'vu', '548', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (240, 'Venezuela (Bolivarian Republic)', 've', '862', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (241, 'Viet Nam', 'vn', '704', 1);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (242, 'Virgin Islands, US', 'vi', '850', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (243, 'Wallis and Futuna Islands', 'wf', '876', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (244, 'Western Sahara', 'eh', '732', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (245, 'Yemen', 'ye', '887', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (246, 'Zambia', 'zm', '894', 0);
INSERT INTO countries (id, name, code, iso_code, tax_treaty) VALUES (247, 'Zimbabwe', 'zw', '716', 0);
--------------------------------------------------------------------------------
PRAGMA foreign_keys = 1;
--------------------------------------------------------------------------------
-- Set new DB schema version
UPDATE settings SET value=27 WHERE name='SchemaVersion';
COMMIT;
