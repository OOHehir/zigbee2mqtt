const {Zcl} = require('zigbee-herdsman');

const definition = {
    zigbeeModel: ['sound_monitor'],
    model: 'sound_monitor',
    vendor: 'DIY',
    description: 'ESP32-C6 SPH0645 Sound Level Monitor',
    fromZigbee: [
        {
            cluster: 'genAnalogInput',
            type: ['attributeReport', 'readResponse'],
            convert: (model, msg, publish, options, meta) => {
                if (msg.data.presentValue !== undefined) {
                    return {sound_level: msg.data.presentValue};
                }
            },
        },
    ],
    toZigbee: [],
    exposes: [
        {
            type: 'numeric',
            name: 'sound_level',
            label: 'Sound level',
            description: 'RMS sound level (0.0-1.0)',
            access: 1,  // STATE_GET
            unit: '',
            value_min: 0,
            value_max: 1,
        },
    ],
};

module.exports = definition;
