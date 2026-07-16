// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyCy0KeyGg4rIweLdPhomLgLwyQzbAOtFGc",
  authDomain: "ufc-website-6a81e.firebaseapp.com",
  projectId: "ufc-website-6a81e",
  storageBucket: "ufc-website-6a81e.firebasestorage.app",
  messagingSenderId: "204941022046",
  appId: "1:204941022046:web:00e697d6b70d1f7b18f5cf",
  measurementId: "G-VGBVKJN96B"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const analytics = getAnalytics(app);

// Initialize Firebase Authentication and get a reference to the service
export const auth = getAuth(app);

// Initialize Cloud Firestore and get a reference to the service
export const db = getFirestore(app);