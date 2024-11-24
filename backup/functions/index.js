/**
 * Import function triggers from their respective submodules:
 *
 * const {onCall} = require("firebase-functions/v2/https");
 * const {onDocumentWritten} = require("firebase-functions/v2/firestore");
 *
 * See a full list of supported triggers at https://firebase.google.com/docs/functions
 */

const {onRequest} = require("firebase-functions/v2/https");
const logger = require("firebase-functions/logger");

// Create and deploy your first functions
// https://firebase.google.com/docs/functions/get-started

// exports.helloWorld = onRequest((request, response) => {
//   logger.info("Hello logs!", {structuredData: true});
//   response.send("Hello from Firebase!");
// });

const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();

// Database reference
const dbRef = admin.firestore().doc('tokens/demo');

// Twitter API init
const TwitterApi = require('twitter-api-v2').default;
const twitterClient = new TwitterApi({
    clientId: 'RXNCVUM0SG1UNUx3a3lfLV9zcmU6MTpjaQ',
    clientSecret: '6mhW7t9Lg8utO1klY6sGAOd4_hUytfksg0XBojBTznIbqGmYmE',
});

const callbackURL = 'http://127.0.0.1:5000/faxnow-app/us-central1/callback';

// OpenAI API init
const { Configuration, OpenAIApi } = require('openai');
const configuration = new Configuration({
    organization: 'GreyBot',
    apiKey: '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',
});
const openai = new OpenAIApi(configuration);

// STEP 1 - Auth URL
exports.auth = functions.https.onRequest((request, response) => {
    const { url, codeVerifier, state } = twitterClient.generateOAuth2AuthLink(
        callbackURL,
        { scope: ['tweet.read', 'tweet.write', 'users.read', 'offline.access'] }
    );

  // store verifier
    await dbRef.set({ codeVerifier, state });

    response.redirect(url);
});

// STEP 2 - Verify callback code, store access_token 
exports.callback = functions.https.onRequest((request, response) => {
    const { state, code } = request.query;

    const dbSnapshot = await dbRef.get();
    const { codeVerifier, state: storedState } = dbSnapshot.data();

    if (state !== storedState) {
        return response.status(400).send('Stored tokens do not match!');
    }

    const {
        client: loggedClient,
        accessToken,
        refreshToken,
    } = await twitterClient.loginWithOAuth2({
        code,
        codeVerifier,
        redirectUri: callbackURL,
    });

    await dbRef.set({ accessToken, refreshToken });

    const { data } = await loggedClient.v2.me(); // start using the client if you want

    response.send(data);
});

// STEP 3 - Refresh tokens and post tweets
exports.tweet = functions.https.onRequest((request, response) => {
    const { refreshToken } = (await dbRef.get()).data();

    const {
        client: refreshedClient,
        accessToken,
        refreshToken: newRefreshToken,
    } = await twitterClient.refreshOAuth2Token(refreshToken);

    await dbRef.set({ accessToken, refreshToken: newRefreshToken });

    const nextTweet = await openai.createCompletion('text-davinci-001', {
        prompt: 'tweet something cool for #techtwitter',
        max_tokens: 64,
    });

    const { data } = await refreshedClient.v2.tweet(
        nextTweet.data.choices[0].text
    );

    response.send(data);
});