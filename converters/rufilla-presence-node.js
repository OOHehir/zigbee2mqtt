const fz = {
    analog_input: {
        cluster: 'genAnalogInput',
        type: ['attributeReport', 'readResponse'],
        convert: (model, msg, publish, options, meta) => {
            const val = msg.data.presentValue;
            if (val === undefined) return;

            switch (msg.endpoint.ID) {
            case 1: return {presence: val > 0.5};
            case 2: return {range_cm: Math.round(val)};
            case 4: return {static_energy: Math.round(val)};
            }
        },
    },
};

const definition = {
    zigbeeModel: ['presence-node-v1'],
    model: 'presence-node-v1',
    vendor: 'Rufilla',
    description: 'Rufilla Intelligence Node — mmWave presence + ToF ranging + static energy',
    fromZigbee: [fz.analog_input],
    toZigbee: [],
    meta: {multiEndpoint: true},
    endpoint: (device) => ({
        presence: 1,
        range_cm: 2,
        static_energy: 4,
    }),
    exposes: [
        {
            type: 'binary',
            name: 'presence',
            property: 'presence',
            value_on: true,
            value_off: false,
            access: 1,
            description: 'Presence detected (mmWave)',
        },
        {
            type: 'numeric',
            name: 'range_cm',
            property: 'range_cm',
            unit: 'cm',
            access: 1,
            description: 'VL53L0X measured range',
        },
        {
            type: 'numeric',
            name: 'static_energy',
            property: 'static_energy',
            unit: '',
            access: 1,
            value_min: 0,
            value_max: 100,
            description: 'LD2410C stationary target energy (0-100)',
        },
    ],
    configure: async (device, coordinatorEndpoint, logger) => {
        for (const ep of [1, 2, 4]) {
            const endpoint = device.getEndpoint(ep);
            if (endpoint) {
                await endpoint.bind('genAnalogInput', coordinatorEndpoint);
            }
        }
    },
};

module.exports = definition;
