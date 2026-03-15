const fz = require('zigbee-herdsman-converters/converters/fromZigbee');
const exposes = require('zigbee-herdsman-converters/lib/exposes');
const reporting = require('zigbee-herdsman-converters/lib/reporting');
const e = exposes.presets;

const definitions = [
    // ── ARST-MS: Multifunction (PIR + reed + temperature + lux) ────
    {
        zigbeeModel: ['ARST-MS'],
        model: 'ARST-MS',
        vendor: 'Arista',
        description: 'Arista Multifunction Sensor — PIR, reed switch, temperature, illuminance',
        fromZigbee: [fz.occupancy, fz.ias_contact_alarm_1, fz.temperature, fz.illuminance, fz.battery],
        toZigbee: [],
        meta: {multiEndpoint: true},
        endpoint: (device) => ({
            occupancy: 1,
            contact: 2,
            temperature: 3,
            illuminance: 4,
        }),
        exposes: [
            e.occupancy().withEndpoint('occupancy'),
            e.contact().withEndpoint('contact'),
            e.temperature().withEndpoint('temperature'),
            e.illuminance().withEndpoint('illuminance'),
            e.battery(),
            e.battery_voltage(),
        ],
        configure: async (device, coordinatorEndpoint, logger) => {
            const ep1 = device.getEndpoint(1);
            const ep2 = device.getEndpoint(2);
            const ep3 = device.getEndpoint(3);
            const ep4 = device.getEndpoint(4);
            await reporting.bind(ep1, coordinatorEndpoint, ['msOccupancySensing', 'genPowerCfg']);
            await reporting.bind(ep2, coordinatorEndpoint, ['ssIasZone']);
            await reporting.bind(ep3, coordinatorEndpoint, ['msTemperatureMeasurement']);
            await reporting.bind(ep4, coordinatorEndpoint, ['msIlluminanceMeasurement']);
        },
    },

    // ── ARST-TH: Temperature & Humidity ────────────────────────────
    {
        zigbeeModel: ['ARST-TH'],
        model: 'ARST-TH',
        vendor: 'Arista',
        description: 'Arista Temperature & Humidity Sensor (SHTC3)',
        fromZigbee: [fz.temperature, fz.humidity, fz.battery],
        toZigbee: [],
        exposes: [
            e.temperature(),
            e.humidity(),
            e.battery(),
            e.battery_voltage(),
        ],
        configure: async (device, coordinatorEndpoint, logger) => {
            const ep1 = device.getEndpoint(1);
            const ep3 = device.getEndpoint(3);
            await reporting.bind(ep1, coordinatorEndpoint, ['genPowerCfg']);
            await reporting.bind(ep3, coordinatorEndpoint, ['msTemperatureMeasurement', 'msRelativeHumidity']);
        },
    },

    // ── ARST-VB: Vibration Sensor ──────────────────────────────────
    {
        zigbeeModel: ['ARST-VB'],
        model: 'ARST-VB',
        vendor: 'Arista',
        description: 'Arista Vibration Sensor (LSM6DSL accelerometer)',
        fromZigbee: [fz.ias_vibration_alarm_1, fz.temperature, fz.battery],
        toZigbee: [],
        exposes: [
            e.vibration(),
            e.temperature(),
            e.battery(),
            e.battery_voltage(),
        ],
        configure: async (device, coordinatorEndpoint, logger) => {
            const ep1 = device.getEndpoint(1);
            const ep2 = device.getEndpoint(2);
            const ep3 = device.getEndpoint(3);
            await reporting.bind(ep1, coordinatorEndpoint, ['genPowerCfg']);
            await reporting.bind(ep2, coordinatorEndpoint, ['ssIasZone']);
            await reporting.bind(ep3, coordinatorEndpoint, ['msTemperatureMeasurement']);
        },
    },
];

module.exports = definitions;
